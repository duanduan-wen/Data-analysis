import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def load_inventory_data(data_dir: Path) -> pd.DataFrame:
    """
    加载并预处理库存数据
    :param data_dir: 数据文件夹路径
    :return: 清洗后的库存汇总表
    """
    # 1. 定义文件路径和对应日期
    file_list = [
        (data_dir / "库存0818.xlsx", "2025-08-18"),
        (data_dir / "库存0819.xlsx", "2025-08-19"),
        (data_dir / "库存0820.xlsx", "2025-08-20")
    ]
    
    # 2. 读取文件并添加日期列
    dfs = []
    dates = []
    for file, date in file_list:
        if not file.exists():
            raise FileNotFoundError(f"库存文件不存在：{file}")
        df = pd.read_excel(file)
        df['日期'] = date
        dfs.append(df)
        dates.append(date)
    
    # 3. 筛选列和行
    keep_columns = [
        "日期","物料号", "物料描述", "规格", "基本单位","工厂",
        "工厂描述","库存地点","可用库存","生产日期","仓库发货限期","到期日期"
    ]
    filtered_dfs = []
    for df in dfs:
        # 筛选列（兼容列名缺失情况）
        df_select_col = df[[col for col in keep_columns if col in df.columns]].copy()
        # 筛选库存地点
        df_final = df_select_col[df_select_col["库存地点"].isin([1001,1002,1099])]
        filtered_dfs.append(df_final)
    
    # 4. 合并数据并重命名列
    df_summary = pd.concat(filtered_dfs, ignore_index=True)
    col_rename = {
        "物料号": "商品编码",
        "物料描述": "商品名称",
        "工厂描述": "仓库名称"
    }
    df_summary.rename(columns=col_rename, inplace=True)
    
    # 5. 补全所有仓库数据（含库存为0的情况）
    all_warehouse_list = [
        "海栗物流合肥仓", "海栗物流北京仓", "海栗物流广州仓",
        "海栗物流阜阳仓", "海栗物流湖南仓", "海栗物流汕头仓",
        "海栗物流上海仓", "海栗物流深圳仓", "海栗物流成都仓"
    ]
    df_summary = df_summary[["日期", "商品编码", "商品名称", "仓库名称","库存地点","可用库存", "到期日期"]]
    
    # 生成全量组合并补全
    all_products = df_summary[["日期", "商品编码", "商品名称"]].drop_duplicates()
    all_warehouses = pd.DataFrame({"仓库名称": all_warehouse_list})
    full_index = all_products.merge(all_warehouses, how="cross")
    df_summary = full_index.merge(
        df_summary,
        on=["日期", "商品编码", "商品名称", "仓库名称"],
        how="left"
    ).fillna({"可用库存": 0,"库存地点": 1001})
    
    # 6. 计算商品状态（过期/临期/常规）
    df_summary['日期'] = pd.to_datetime(df_summary['日期'])
    df_summary['到期日期'] = pd.to_datetime(df_summary['到期日期'], errors='coerce')
    df_summary['剩余天数'] = (df_summary['到期日期'] - df_summary['日期']).dt.days
    # 状态判断
    df_summary['状态'] = np.where(
        df_summary['剩余天数'] < 0, '过期',
        np.where(df_summary['剩余天数'] < 180, '临期', '常规')
    )
    # 标记判断（在途/采购/库存）
    df_summary['标记'] = np.where(
        df_summary['库存地点'] == 1002, '在途',
        np.where(df_summary['库存地点'] == 1099, '采购', '库存')
    )
    
    # 7. 采购标记库存放大（业务规则）
    df_summary_temp = df_summary.copy()
    df_summary_temp.loc[df_summary_temp["标记"] == "采购", "可用库存"] *= 100
    
    return df_summary, df_summary_temp

def load_sales_data(data_dir: Path, goods_list: list) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    加载并预处理销售数据
    :param data_dir: 数据文件夹路径
    :param goods_list: 库存表中的商品列表（用于过滤）
    :return: 销售趋势数据(df_agg)、帕累托分析数据(df_total)
    """
    # 1. 读取销售数据
    sale_file = data_dir / "25-区域-日.xlsx"
    if not sale_file.exists():
        raise FileNotFoundError(f"销售文件不存在：{sale_file}")
    df_sale = pd.read_excel(sale_file)
    
    # 2. 清洗列名和日期
    df_sale.columns = df_sale.columns.str.replace(r'[↑↓⇓⇑]', '', regex=True).str.strip()
    df_sale['日期'] = pd.to_datetime(df_sale['序号'], format='%Y%m%d', errors='coerce')
    
    # 3. 筛选时间范围和商品
    start_date = '2025-07-18'
    end_date = '2025-07-24'
    df_sale_filtered = df_sale[
        (df_sale['日期'] >= start_date) & 
        (df_sale['日期'] <= end_date) & 
        (df_sale['商品名称'].isin(goods_list))
    ].copy()
    
    # 4. 聚合全国销售数据
    df_agg = df_sale_filtered.groupby(['商品名称', '日期'], as_index=False)['销售数量'].sum()
    df_agg['日期'] = pd.to_datetime(df_agg['日期'])
    df_agg = df_agg.sort_values('日期')
    
    df_total = df_agg.groupby('商品名称', as_index=False)['销售数量'].sum()
    df_total = df_total.sort_values('销售数量', ascending=False).reset_index(drop=True)
    
    return df_sale_filtered, df_agg, df_total

def calculate_inventory_days(df_summary: pd.DataFrame, df_sale_filtered: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    计算库存可用天数（核心业务指标）
    :param df_summary: 库存表
    :param df_sale_filtered: 销售表
    :return: 明细结果(df_result)、商品汇总(df_total)
    """
    # 1. 区域-仓库映射
    region_to_warehouse = {
        "安徽区域": "海栗物流合肥仓", "北京区域": "海栗物流北京仓",
        "广州区域": "海栗物流广州仓", "河南区域": "海栗物流阜阳仓",
        "湖南区域": "海栗物流湖南仓", "环粤区域": "海栗物流汕头仓",
        "江西区域": "海栗物流湖南仓", "上海区域": "海栗物流上海仓",
        "深圳区域": "海栗物流深圳仓", "四川区域": "海栗物流成都仓"
    }
    
    # 2. 销售表关联仓库
    df_sale_inventory = df_sale_filtered.copy()
    df_sale_inventory["仓库名称"] = df_sale_inventory["区域名称"].map(region_to_warehouse)
    
    # 3. 计算日均销量（7天）
    df_daily = df_sale_inventory.groupby(["仓库名称", "商品编码"]).agg({
        "销售数量": "sum"
    }).reset_index()
    df_daily["日均销售"] = df_daily["销售数量"] / 7  # 可优化为动态计算天数
    
    # 4. 合并库存和销售数据
    df_result = pd.merge(
        df_summary, df_daily,
        on=["仓库名称", "商品编码"],
        how="inner"
    )
    
    # 5. 计算可用天数（处理除零）
    df_result["可用天数"] = df_result.apply(
        lambda x: round(x["可用库存"] / x["日均销售"], 1) if x["日均销售"] > 0 else 0,
        axis=1
    )
    
    # 6. 总可用天数（按商品汇总）
    df_total_days = df_result.groupby("商品编码")["可用天数"].mean().reset_index()
    df_total_days.rename(columns={"可用天数": "总可用天数"}, inplace=True)
    df_result = pd.merge(df_result, df_total_days, on="商品编码")
    
    # 7. 标准天数配置（业务规则）
    standard_map = {
        3000513: 20, 3000529: 20, 3000534: 20,
        3000549: 20, 3000550: 20, 3000604: 20
    }
    df_result["标准天数"] = df_result["商品编码"].map(standard_map)
    
    # 8. 商品维度汇总（8月18日+1001库）
    df_temp = df_result[(df_result["日期"] == "2025-08-18") & (df_result["库存地点"] == 1001)].copy()
    df_total = df_temp.groupby("商品名称").agg(
        库存总数=("可用库存", "sum"),
        日均销售总数=("日均销售", "sum"),
        标准天数=("标准天数", "mean")
    ).reset_index()
    df_total["可用天数"] = (df_total["库存总数"] / df_total["日均销售总数"]).round(0).astype(int)
    
    # 9. 仓库维度汇总
    df_warehouse = df_temp.groupby(["商品名称", "仓库名称"]).agg(
        库存总数=("可用库存", "sum"),
        日均销售总数=("日均销售", "sum")
    ).reset_index()
    df_warehouse["可用天数"] = (df_warehouse["库存总数"] / df_warehouse["日均销售总数"]).round().astype(int)
    df_warehouse = df_warehouse.merge(
        df_total[["商品名称", "标准天数","可用天数"]].rename(columns={"可用天数": "全国可用天数"}),
        on="商品名称",
        how="left"
    )
    
    return df_result, df_total, df_warehouse