import plotly.graph_objects as go
import plotly.express as px
import plotly.colors as pc
import pandas as pd
import numpy as np
from pathlib import Path

def create_inventory_status_pie(df_summary: pd.DataFrame, output_dir: Path):
    """
    生成商品库存状态交互饼图（过期/临期/常规）
    :param df_summary: 库存表
    :param output_dir: 输出文件夹
    """
    all_goods = sorted(df_summary['商品名称'].unique())
    fig = go.Figure()
    
    for good in all_goods:
        df_sel = df_summary[df_summary['商品名称'] == good].copy()
        df_plot = df_sel.groupby('状态', as_index=False).agg(
            数量=('状态', 'count'),
            仓库列表=('仓库名称', lambda x: ', '.join(x.unique()))
        )
        
        fig.add_pie(
            labels=df_plot['状态'],
            values=df_plot['数量'],
            customdata=df_plot['仓库列表'],
            name=good,
            visible=False
        )
    
    # 默认显示第一个商品
    if len(fig.data) > 0:
        fig.data[0].visible = True

    fig.update_layout(
        title="商品库存状态分布",
        title_x=0.5,
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                showactive=True,
                x=0.05, y=1.5,
                xanchor="left", yanchor="top",
                buttons=[
                    dict(
                        label=good,
                        method="update",
                        args=[
                            {"visible": [g == good for g in all_goods]},
                            {"title": f"商品：{good} 库存状态分布"}
                        ]
                    ) for good in all_goods
                ]
            )
        ]
    )
    
    fig.update_traces(
        hovertemplate='状态：%{label}<br>仓库：%{customdata} '
    )
    fig.write_html(output_dir / "inventory_status_pie.html")
    fig.show()

def create_inventory_bar(df_summary_temp: pd.DataFrame, output_dir: Path):
    """
    生成仓库标记占比堆叠柱状图
    :param df_summary_temp: 库存表（含采购放大）
    :param output_dir: 输出文件夹
    """
    # 数据聚合
    df_agg = df_summary_temp.groupby(['商品名称', '仓库名称', '标记'], as_index=False)['可用库存'].sum()
    df_agg['仓库总和'] = df_agg.groupby(['商品名称', '仓库名称'])['可用库存'].transform('sum')
    df_agg['占比(%)'] = df_agg['可用库存'] / df_agg['仓库总和'] * 100
    
    global_warehouses = sorted(df_agg['仓库名称'].unique())
    all_goods = sorted(df_agg['商品名称'].unique())
    
    # 构建图表
    fig = go.Figure()
    goods_traces_map = {}

    for good in all_goods:
        df_good = df_agg[df_agg['商品名称'] == good].copy()
        marks = df_good['标记'].unique()
        trace_indices = []

        for mark in marks:
            df_mark = df_good[df_good['标记'] == mark]
            y_values = [
                df_mark[df_mark['仓库名称'] == w]['占比(%)'].iloc[0] 
                if w in df_mark['仓库名称'].values else 0 
                for w in global_warehouses
            ]
            custom_data = [
                df_mark[df_mark['仓库名称'] == w]['可用库存'].iloc[0] 
                if w in df_mark['仓库名称'].values else 0 
                for w in global_warehouses
            ]

            trace = go.Bar(
                x=global_warehouses,
                y=y_values,
                name=mark,
                visible=False,
                hovertemplate=f'商品：{good}<br>仓库：%{{x}}<br>标记：{mark}<br>占比：%{{y:.1f}}%<br>可用库存：%{{customdata}}',
                customdata=custom_data
            )
            fig.add_trace(trace)
            trace_indices.append(len(fig.data) - 1)

        goods_traces_map[good] = trace_indices

    # 默认显示第一个商品
    if all_goods:
        for idx in goods_traces_map[all_goods[0]]:
            fig.data[idx].visible = True

    # 布局配置
    fig.update_layout(
        title="商品各仓库标记占比分布（百分比堆叠柱）",
        title_x=0.5,
        barmode='stack',
        yaxis=dict(tickformat='.0f%%', title='标记占比', range=[0,100]),
        xaxis=dict(title='仓库名称', categoryorder='array', categoryarray=global_warehouses),
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                showactive=True,
                x=0.02, y=1.4,
                xanchor="left", yanchor="top",
                buttons=[
                    dict(
                        label=good,
                        method="update",
                        args=[
                            {"visible": [i in goods_traces_map[good] for i in range(len(fig.data))]},
                            {"title": f"商品：{good} 各仓库标记占比分布"}
                        ]
                    ) for good in all_goods
                ]
            )
        ]
    )

    fig.write_html(output_dir / "inventory_mark_stacked_bar.html")
    fig.show()

def create_sales_line_chart(df_agg: pd.DataFrame, output_dir: Path):
    """
    生成商品销售趋势折线图（圆滑曲线）
    :param df_agg: 销售趋势数据
    :param output_dir: 输出文件夹
    """
    all_goods = sorted(df_agg['商品名称'].unique())
    fig = go.Figure()
    goods_traces_map = {}

    for good in all_goods:
        df_good = df_agg[df_agg['商品名称'] == good]
        trace = go.Scatter(
            x=df_good['日期'], y=df_good['销售数量'], name=good, visible=False,
            line=dict(shape='spline'),
            mode='lines+markers+text',
            marker=dict(size=8, color='blue', line=dict(color='darkblue', width=2)),
            text=df_good['销售数量'].astype(int),
            textposition='top center', texttemplate='%{text}'
        )
        fig.add_trace(trace)
        goods_traces_map[good] = [len(fig.data)-1]

    # 默认显示第一个商品
    if all_goods:
        fig.data[goods_traces_map[all_goods[0]][0]].visible = True

    # 布局配置
    y_min = df_agg['销售数量'].min() - 10 if not df_agg['销售数量'].empty else 0
    y_max = df_agg['销售数量'].max() + 10 if not df_agg['销售数量'].empty else 100
    fig.update_layout(
        title="商品全国销售趋势", title_x=0.5,
        xaxis=dict(title='日期', tickformat='%Y-%m-%d'),
        yaxis=dict(title='销售数量', range=[y_min, y_max]),
        margin=dict(b=100),
        updatemenus=[dict(
            type="dropdown", x=0.02, y=1.4, xanchor="left", yanchor="top",
            buttons=[dict(label=g, method="update",
            args=[{"visible": [i in goods_traces_map[g] for i in range(len(fig.data))]},
                  {"title": f"商品：{g} 销售趋势"}]) for g in all_goods]
        )]
    )
    fig.write_html(output_dir / "sales_trend_line.html")
    fig.show()

def create_pareto_chart(df_total: pd.DataFrame, output_dir: Path):
    """
    生成销售帕累托分析图（ABC分析）
    :param df_total: 销售汇总数据
    :param output_dir: 输出文件夹
    """
    # 计算累计占比
    total_sales = df_total['销售数量'].sum()
    df_total['累计占比'] = df_total['销售数量'].cumsum() / total_sales * 100

    fig = go.Figure()
    # 销量柱状图
    fig.add_bar(x=df_total['商品名称'], y=df_total['销售数量'], name='总销量')
    # 累计占比折线（双Y轴）
    fig.add_scatter(
        x=df_total['商品名称'], y=df_total['累计占比'], name='累计占比(%)',
        yaxis='y2', line=dict(shape='spline', color='red'),
        hovertemplate='商品：%{x}<br>累计占比：%{y:.1f}%<extra></extra>'
    )

    # 布局配置
    fig.update_layout(
        title="商品销售帕累托ABC分析",
        title_x=0.5,
        yaxis=dict(title='销售数量'),
        yaxis2=dict(
            title='累计占比(%)',
            overlaying='y',
            side='right',
            range=[0, 105]
        ),
        xaxis=dict(tickangle=-45, title='商品名称'),
        margin=dict(b=150, r=120),
        legend=dict(
            x=1.02, y=5.0,
            xanchor='left', yanchor='top'
        ),
    )
    fig.write_html(output_dir / "sales_pareto_chart.html")
    fig.show()

def create_product_day_chart(df_total: pd.DataFrame, output_dir: Path):
    """
    生成商品可用天数vs标准天数对比图
    :param df_total: 商品汇总数据
    :param output_dir: 输出文件夹
    """
    fig = go.Figure()
    
    # 柱状图：总可用天数
    fig.add_trace(go.Bar(
        x=df_total["商品名称"],
        y=df_total["可用天数"],
        name="总可用天数",
        marker_color="#1f77b4",
        text=df_total["可用天数"],
        textposition="outside",
        textfont=dict(color="black", size=12),
        hovertemplate="商品: %{x}<br>总可用天数: %{y}天<extra></extra>"
    ))
    
    # 折线图：标准天数
    fig.add_trace(go.Scatter(
        x=df_total["商品名称"],
        y=df_total["标准天数"],
        name="标准天数",
        mode="lines+markers",
        line=dict(color="#dc3912", width=3),
        marker=dict(size=8),
        hovertemplate="商品: %{x}<br>标准天数: %{y}天<extra></extra>"
    ))
    
    # 布局配置
    fig.update_layout(
        height=500,
        plot_bgcolor="white",
        paper_bgcolor="white",
        title=dict(
            text="商品库存可用天数 vs 标准天数",
            x=0.5,
            y=0.95),
        xaxis_title="商品名称",
        yaxis_title="可用天数",
        legend=dict(
            font=dict(color="black"),
            bgcolor="white",
            bordercolor="black",
            borderwidth=1),
        )
    fig.write_html(output_dir / "product_inventory_days.html")
    fig.show()

def get_bar_colors(df: pd.DataFrame) -> list:
    """辅助函数：根据可用天数判断柱状图颜色"""
    colors = []
    for _, row in df.iterrows():
        if pd.isna(row["可用天数"]) or pd.isna(row["标准天数"]):
            colors.append("#808080")  # 灰色：数据缺失
        elif row["可用天数"] < row["标准天数"]:
            colors.append("#ff4c4c")   # 红色：不足
        else:
            colors.append("#1f77b4")   # 蓝色：达标
    return colors

def create_product_warehouse_day_chart(df_warehouse: pd.DataFrame, output_dir: Path):
    """
    生成仓库维度可用天数对比图（带下拉交互）
    :param df_warehouse: 仓库维度数据
    :param output_dir: 输出文件夹
    """
    # 预处理商品列表
    product_list = df_warehouse["商品名称"].unique().tolist()
    product_data = {}
    
    for product in product_list:
        df_temp = df_warehouse[df_warehouse["商品名称"] == product].copy()
        # 类型转换确保数值判断正确
        df_temp["可用天数"] = pd.to_numeric(df_temp["可用天数"], errors="coerce")
        df_temp["标准天数"] = pd.to_numeric(df_temp["标准天数"], errors="coerce")
        df_temp = df_temp.sort_values(by="可用天数", ascending=False)
        
        product_data[product] = {
            "df": df_temp,
            "national_days": df_temp["全国可用天数"].iloc[0] if not df_temp.empty else 0
        }

    # 构建图表
    fig = go.Figure()

    # 默认展示第一个商品
    first_p = product_list[0] if product_list else ""
    if first_p:
        df_first = product_data[first_p]["df"]
        national_first = product_data[first_p]["national_days"]
        colors_first = get_bar_colors(df_first)
        
        # 柱状图：仓库可用天数
        fig.add_trace(go.Bar(
            x=df_first["仓库名称"],
            y=df_first["可用天数"],
            name="仓库可用天数",
            marker_color=colors_first,
            text=df_first["可用天数"],
            textposition="outside"
        ))
        
        # 折线图：全国可用天数
        fig.add_trace(go.Scatter(
            x=df_first["仓库名称"],
            y=[national_first] * len(df_first),
            mode="lines+markers",
            name="全国可用天数",
            line=dict(color="orange", width=3)
        ))

    # 下拉按钮配置
    dropdown_buttons = []
    for prod in product_list:
        df_p = product_data[prod]["df"]
        national_p = product_data[prod]["national_days"]
        colors_p = get_bar_colors(df_p)
    
        q95 = df_p["可用天数"].quantile(0.95) if not df_p.empty else 50
        y_max = max(q95, 50)
        
        dropdown_buttons.append(dict(
            label=prod,
            method="update",
            args=[{
                "x": [df_p["仓库名称"], df_p["仓库名称"]],
                "y": [df_p["可用天数"], [national_p]*len(df_p)],
                "text": [df_p["可用天数"], None],
                "marker.color": [colors_p, None],
            },
            {"title": f"{prod} 仓库可用天数 & 全国可用天数",
             "yaxis.range": [0, y_max]
            }]
        ))
    
    # 布局配置
    if first_p:
        q95_first = product_data[first_p]["df"]["可用天数"].quantile(0.95)
        y_max_first = max(q95_first, 50)
    else:
        y_max_first = 50
    
    fig.update_layout(
        title=dict(text=f"{first_p} 仓库可用天数 & 全国可用天数", x=0.5) if first_p else "",
        xaxis_title="仓库名称",
        yaxis_title="可用天数",
        yaxis=dict(range=[0, y_max_first], rangemode="nonnegative"),
        height=600,
        plot_bgcolor="white",
        updatemenus=[dict(
            type="dropdown", x=0.1, y=1.15,
            bgcolor="white", buttons=dropdown_buttons
        )]
    )
    fig.write_html(output_dir / "warehouse_inventory_days.html")
    fig.show()