from pathlib import Path
import sys

# 添加当前目录到Python路径（确保模块导入）
sys.path.append(str(Path(__file__).parent.parent))

from src.data_processing import (
    load_inventory_data, load_sales_data, calculate_inventory_days
)
from src.visualization import (
    create_inventory_status_pie, create_inventory_bar,
    create_sales_line_chart, create_pareto_chart,
    create_product_day_chart, create_product_warehouse_day_chart
)

def main():
    """主函数：一键执行库存与销售全流程分析"""
    # 1. 定义路径（项目根目录）
    root_dir = Path(__file__).parent.parent
    data_dir = root_dir / "data"
    output_dir = root_dir / "output"
    
    # 创建输出文件夹
    output_dir.mkdir(exist_ok=True)
    
    print("===== 1. 加载并预处理库存数据 =====")
    df_summary, df_summary_temp = load_inventory_data(data_dir)
    print(f"库存数据加载完成，数据量：{len(df_summary)} 行")
    
    print("===== 2. 加载并预处理销售数据 =====")
    goods_list = df_summary['商品名称'].unique().tolist()
    df_sale_filtered, df_agg, df_total = load_sales_data(data_dir, goods_list)
    print(f"销售数据加载完成，筛选后数据量：{len(df_sale_filtered)} 行")
    
    print("===== 3. 计算核心业务指标（可用天数） =====")
    df_result, df_product_total, df_warehouse = calculate_inventory_days(df_summary, df_sale_filtered)
    print(f"业务指标计算完成，商品汇总数据量：{len(df_product_total)} 行")
    
    print("===== 4. 生成可视化图表 =====")
    # 4.1 库存状态饼图
    create_inventory_status_pie(df_summary, output_dir)
    # 4.2 仓库标记堆叠柱图
    create_inventory_bar(df_summary_temp, output_dir)
    # 4.3 销售趋势折线图
    create_sales_line_chart(df_agg, output_dir)
    # 4.4 销售帕累托图
    create_pareto_chart(df_total, output_dir)
    # 4.5 商品可用天数对比图
    create_product_day_chart(df_product_total, output_dir)
    # 4.6 仓库可用天数对比图
    create_product_warehouse_day_chart(df_warehouse, output_dir)
    
    print("===== 5. 分析完成 =====")
    print(f"所有可视化结果已保存至：{output_dir.absolute()}")
    print("核心输出文件：")
    for file in output_dir.glob("*.html"):
        print(f"  - {file.name}")

if __name__ == "__main__":
    main()