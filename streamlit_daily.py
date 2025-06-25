import pandas as pd 
from datetime import datetime, timedelta 
import streamlit as st 
import plotly.express  as px 
import plotly.graph_objects  as go 
from streamlit import cache_data, cache_resource 
import akshare as ak

# 页面配置
st.set_page_config(layout="wide") 
st.markdown(""" 
<style>
    .main > div {max-width: none; padding:2rem 4rem !important;}
    .stPlotlyChart {height:450px !important; margin:-1rem;}
    [data-testid="stHorizontalBlock"] {gap:2rem;}
    .st-emotion-cache-1r4qj8v {padding-top:3rem;}
</style>
""", unsafe_allow_html=True)

# 数据加载函数
@cache_data(ttl=timedelta(hours=1), show_spinner="正在加载数据...")
def load_data():
    # 从Excel文件加载数据
    cbond_msg = pd.read_excel('./data/cbond_stock_daily_data.xlsx', sheet_name='cbond_msg')
    cbond_data = pd.read_excel('./data/cbond_stock_daily_data.xlsx', sheet_name='可转债数据')
    stock_data = pd.read_excel('./data/cbond_stock_daily_data.xlsx', sheet_name='正股数据')
    conversion_price_data = pd.read_excel('./data/cbond_stock_daily_data.xlsx', sheet_name='conversion_price_data')
    
    # 转换日期格式
    cbond_data['day'] = pd.to_datetime(cbond_data['day']).dt.date
    stock_data['day'] = pd.to_datetime(stock_data['day']).dt.date
    
    # 合并数据
    stock_data = stock_data.merge(cbond_msg[['cbond_code', 'stock_code']], on='stock_code', how='left')
    
    # 计算每个日期的转股价映射
    date_mappings = {}
    for date in cbond_data['day'].unique():
        date_mappings[date] = get_conversion_price_mapping(date, conversion_price_data)
    
    # 合并正股数据到可转债数据
    merged_data = cbond_data.merge(
        stock_data[['day', 'cbond_code', 'close', 'volume']],
        on=['day', 'cbond_code'],
        how='left',
        suffixes=('', '_stock')
    )
    
    # 计算溢价率
    merged_data['premium_rate'] = merged_data.apply(
        lambda x: calculate_real_time_premium_rate(
            x['close'],
            x['close_stock'],
            date_mappings[x['day']][x['cbond_code']]
        ),
        axis=1
    )
    cbond_data = merged_data
    
    return cbond_data, stock_data, cbond_msg


# 溢价率计算函数
def calculate_real_time_premium_rate(cbond_price, stock_price, conversion_price):
    conversion_value = (stock_price / conversion_price) * 100
    if conversion_value == 0:
        return 0
    premium_rate = (cbond_price - conversion_value) / conversion_value * 100
    return premium_rate

# 转股价映射函数
def get_conversion_price_mapping(date, conversion_price_data):
    date = pd.to_datetime(date)
    grouped = conversion_price_data.groupby('symbol')
    result = []
    
    for symbol, group in grouped:
        if len(group) == 1:
            result.append(group)
            continue
            
        filtered = group[pd.to_datetime(group['change_date']) <= date]
        if not filtered.empty:
            latest = filtered.sort_values('change_date', ascending=False).iloc[0]
        else:
            latest = group.sort_values('change_date', ascending=False).iloc[0]
        result.append(pd.DataFrame([latest]))

    newest_change_data = pd.concat(result).reset_index(drop=True)
    newest_change_data.rename(columns={'symbol':'cbond_code'}, inplace=True)
    conversion_prices_mapping = newest_change_data.set_index('cbond_code')['conversion_price'].to_dict()
    return conversion_prices_mapping

# K线图创建函数
def create_fullwidth_kline(data, title):
    valid_data = data.dropna(subset=['open', 'high', 'low', 'close'])
    if valid_data.empty:
        return go.Figure()
    
    # 创建主K线图
    fig = go.Figure()
    
    # 先添加K线图
    fig.add_trace(go.Candlestick(
        x=valid_data.index,
        open=valid_data['open'],
        high=valid_data['high'],
        low=valid_data['low'],
        close=valid_data['close'],
        increasing_line_color='#EF5350',
        decreasing_line_color='#26A69A',
        hoverinfo='x+y',
        name='价格'
    ))
    
    # 后添加成交量柱状图，并设置透明度
    fig.add_trace(go.Bar(
        x=valid_data.index,
        y=valid_data['volume'],
        name='成交量',
        marker_color='#7f8c8d',
        opacity=0.3,  # 设置透明度
        yaxis='y2'
    ))
    
    fig.update_layout(
        height=450,
        margin=dict(l=0, r=0, t=50, b=20),
        xaxis=dict(
            type='category',
            showticklabels=False,
            showgrid=False,
            zeroline=False,
            rangeslider=dict(visible=False)
        ),
        yaxis=dict(
            gridcolor='#E0E0E0',
            showgrid=True,
            tickformat=',.0f',
            title='价格'
        ),
        yaxis2=dict(
            title='成交量',
            overlaying='y',
            side='right',
            showgrid=False
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        title=dict(
            text=f'<b>{title}</b>',
            x=0.05,
            font=dict(size=18, color='#2c3e50'),
            xanchor='left'
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )
    
    fig.add_annotation(
        x=0, y=-0.12,
        xref='paper', yref='paper',
        showarrow=False,
        font=dict(color='#7f8c8d', size=12)
    )
    
    return fig

# 溢价率走势图创建函数
def create_premium_rate_line(data, title):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data.index,
        y=data['premium_rate'],
        mode='lines',
        name='溢价率',
        line=dict(color='#2196F3')
    ))
    
    fig.update_layout(
        height=450,
        margin=dict(l=0, r=0, t=50, b=20),
        xaxis=dict(
            type='category',
            showticklabels=False,
            showgrid=False,
            zeroline=False
        ),
        yaxis=dict(
            gridcolor='#E0E0E0',
            showgrid=True,
            tickformat=',.2f',
            title='溢价率(%)'
        ),
        plot_bgcolor='rgba(0,0,0,0)',
        hovermode='x unified',
        title=dict(
            text=f'<b>{title}</b>',
            x=0.05,
            font=dict(size=18, color='#2c3e50'),
            xanchor='left'
        )
    )
    
    return fig

# 主函数
def main():
    st.title("可转债全景分析系统")
    
    # 加载数据
    cbond_data, stock_data, cbond_msg = load_data()
    
    # 条件筛选面板
    with st.form("filter_form"):
        # 先根据溢价率筛选初始可转债
        init_filtered_cbonds = cbond_data[
            (cbond_data['premium_rate'] >= -0.3) &
            (cbond_data['premium_rate'] <= 0.10)
        ]['cbond_code'].unique()
        
        # 获取初始可转债名称列表（取溢价率和名称的交集）
        init_selected = cbond_msg[
            cbond_msg['cbond_code'].isin(init_filtered_cbonds)
        ]['cbond_display_name'].to_list()
        
        # 可转债选择器
        selected = st.multiselect("选择可转债", cbond_msg['cbond_display_name'].unique(), default=init_selected)
        
        # 溢价率筛选
        min_premium, max_premium = st.slider(
            "溢价率范围 (%)",
            min_value=float(cbond_data['premium_rate'].min()),
            max_value=float(cbond_data['premium_rate'].max()),
            value=(-0.3, 0.10)
        )
        
        date_range = st.date_input("日期范围", [
            datetime.now() - timedelta(days=90),
            datetime.now()
        ], key='date_selector')
        
        # 提交按钮
        submitted = st.form_submit_button("查询")
    
    if submitted:
        # 根据溢价率筛选可转债
        filtered_cbonds = cbond_data[
            (cbond_data['premium_rate'] >= min_premium) &
            (cbond_data['premium_rate'] <= max_premium)
        ]['cbond_code'].unique()
        
        # 更新selected列表，取名称和溢价率的交集
        selected = [name for name in selected if cbond_msg[cbond_msg['cbond_display_name'] == name]['cbond_code'].iloc[0] in filtered_cbonds]
 
    # 主展示区
    for name in selected:
        if name.startswith('Z'):
            continue
        
        cbond_code = cbond_msg[cbond_msg['cbond_display_name'] == name]['cbond_code'].iloc[0]
        stock_code = cbond_msg[cbond_msg['cbond_code'] == cbond_code]['stock_code'].iloc[0]
        stock_name = stock_data[stock_data['stock_code'] == stock_code]['name'].iloc[0]
        # 获取历史数据
        bond_history = cbond_data[
            (cbond_data['cbond_code'] == cbond_code) & 
            (cbond_data['day'] >= date_range[0]) &
            (cbond_data['day'] <= date_range[1])
        ].set_index('day')
        
        stock_history = stock_data[
            (stock_data['stock_code'] == stock_code) & 
            (stock_data['day'] >= date_range[0]) &
            (stock_data['day'] <= date_range[1])
        ].set_index('day')
        

        # 创建对比布局 
        with st.container(border=True):
            # 第一行：K线图三栏布局
            row1_col1, row1_col2, row1_col3 = st.columns([1,1,1])
            with row1_col1:
                st.plotly_chart(
                    create_fullwidth_kline(bond_history, f"{name}价格走势"),
                    use_container_width=True
                )
            with row1_col2:
                st.plotly_chart(
                    create_fullwidth_kline(stock_history, f"{stock_name}价格走势"),
                    use_container_width=True
                )
            with row1_col3:
                st.plotly_chart(
                    create_premium_rate_line(bond_history, "溢价率走势"),
                    use_container_width=True
                )

            # 第二行：指标卡布局
            row2_col1, row2_col2, row2_col3 = st.columns([1,1,2])
            with row2_col1:
                if len(bond_history) > 0:
                    delta = (bond_history['close'].iloc[-1] - bond_history['close'].iloc[0]) / bond_history['close'].iloc[0]
                    st.metric(" 可转债累计涨跌",
                             f"{delta:.2%}",
                             delta=f"{delta:.2%}",
                             help="选定时间段内价格变动幅度")
                else:
                    st.metric(" 可转债累计涨跌", "N/A", help="无有效数据")
            with row2_col2:
                if len(stock_history) > 0:
                    stock_delta = (stock_history['close'].iloc[-1] - stock_history['close'].iloc[0]) / stock_history['close'].iloc[0]
                    st.metric(" 正股累计涨跌",
                             f"{stock_delta:.2%}",
                             delta=f"{stock_delta:.2%}",
                             help="正股同期价格变动幅度")
                else:
                    st.metric("正股累计涨跌", "N/A", help="无有效数据")
            with row2_col3:
                if len(bond_history) > 0:
                    latest_premium_rate = bond_history[bond_history.index == bond_history.index[-1]]['premium_rate'].iloc[0]
                    st.metric("最新溢价率", f"{latest_premium_rate:.2f}%", delta=f"{latest_premium_rate:.2f}%", help="选定日期最新溢价率")
                else:
                    st.metric("最新溢价率", "N/A", help="无有效数据")

        st.divider()


if __name__ == '__main__':
    main()