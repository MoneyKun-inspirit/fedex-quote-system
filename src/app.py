import streamlit as st
import sys
import os
import json

# 添加src目录到路径，方便导入引擎
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from engine import PricingEngine

# 设置页面配置 (必须在第一行)
st.set_page_config(
    page_title="Starmerx 物流智能报价中枢", 
    page_icon="🌍", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 自定义 CSS 注入 (科技感、跨境电商风格) ---
st.markdown("""
<style>
    /* 全局背景与字体 */
    .stApp {
        background-color: #f4f7f6;
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* 顶栏隐藏 */
    header {visibility: hidden;}
    
    /* 标题样式 */
    .main-title {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.5rem;
        text-align: center;
        letter-spacing: 1px;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #64748B;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* 卡片容器样式 */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background-color: white;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: none !important;
        padding: 1.5rem !important;
        transition: transform 0.2s ease;
    }
    div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    
    /* 按钮样式强化 */
    .stButton > button {
        background: linear-gradient(135deg, #2563EB 0%, #1E40AF 100%);
        color: white;
        font-weight: 600;
        border-radius: 8px;
        border: none;
        padding: 0.75rem 0;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.4);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #1D4ED8 0%, #1E3A8A 100%);
        box-shadow: 0 6px 8px -1px rgba(37, 99, 235, 0.6);
        transform: translateY(-1px);
    }
    
    /* 侧边栏样式 */
    section[data-testid="stSidebar"] {
        background-color: #1e293b;
    }
    
    /* 侧边栏所有文本和标签强制变为白色，提高对比度 */
    section[data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }
    
    /* 侧边栏输入框文字颜色(为了在白底输入框中能看清，单独设置黑色) */
    section[data-testid="stSidebar"] input {
        color: #0f172a !important;
        background-color: white !important;
    }
    
    /* 侧边栏数字输入框的外层包裹器颜色修复 (防止被全局影响) */
    section[data-testid="stSidebar"] div[data-baseweb="input"] {
        background-color: white !important;
        border-color: #cbd5e1 !important;
    }
    
    /* 侧边栏数字输入框的加减按钮颜色修复 */
    section[data-testid="stSidebar"] button[kind="stepUp"], 
    section[data-testid="stSidebar"] button[kind="stepDown"] {
        color: #0f172a !important;
        background-color: white !important;
    }
    
    /* 侧边栏按钮样式覆盖 (保存配置按钮) */
    section[data-testid="stSidebar"] .stButton > button {
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
        margin-top: 10px;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: linear-gradient(135deg, #60A5FA 0%, #3B82F6 100%) !important;
    }
    
    /* 账单金额高亮 */
    .highlight-price {
        font-size: 2.2rem;
        font-weight: 800;
        color: #059669; /* 翡翠绿 */
        margin: 1rem 0;
    }
    
    /* 小标签样式 */
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #334155;
        border-left: 4px solid #3B82F6;
        padding-left: 10px;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    
    /* 打字机特效副标题 */
    .typing-effect {
        overflow: hidden;
        border-right: .15em solid #3B82F6;
        white-space: nowrap;
        margin: 0 auto;
        letter-spacing: .15em;
        animation: typing 3.5s steps(40, end), blink-caret .75s step-end infinite;
    }
    
    @keyframes typing {
        from { width: 0 }
        to { width: 100% }
    }
    @keyframes blink-caret {
        from, to { border-color: transparent }
        50% { border-color: #3B82F6; }
    }
</style>

<!-- 引入 Particles.js 粒子动画背景 -->
<div id="particles-js" style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1;"></div>
<script src="https://cdn.jsdelivr.net/particles.js/2.0.0/particles.min.js"></script>
<script>
    // 由于 Streamlit 的机制，直接写 script 可能被拦截，这里我们利用 components.html 或 hack 的方式加载
    // 但更安全的方式是通过纯 CSS 动画实现动态背景
</script>

<!-- 纯 CSS 动态波浪/星空背景 -->
<style>
    .stApp {
        background: linear-gradient(-45deg, #e0eafc, #cfdef3, #f4f7f6, #e6f0fa);
        background-size: 400% 400%;
        animation: gradientBG 15s ease infinite;
    }
    @keyframes gradientBG {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
</style>
""", unsafe_allow_html=True)

# 初始化引擎
@st.cache_resource
def load_engine():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir)
    rate_file = os.path.join(project_dir, '星商FedEx2026最新折后报价单.xlsx')
    das_file = os.path.join(current_dir, 'data_parsers', 'das_database.json')
    rules_file = os.path.join(current_dir, 'rules.json')
    return PricingEngine(rate_file, das_file, rules_file)

try:
    engine = load_engine()
except Exception as e:
    st.error(f"引擎加载失败: {e}")
    st.stop()

# 页面标题
st.markdown('<div class="main-title">🌍 Starmerx 物流智能报价中枢</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title"><div class="typing-effect">FedEx Automated Quoting System (2026 Edition) | 精准算价 · 降本增效</div></div>', unsafe_allow_html=True)
st.markdown("---")

# 侧边栏：系统配置快速预览与修改
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/fedex.png", width=60)
    st.header("⚙️ 费率与策略中枢")
    st.markdown("在这里调整全局参数，实时生效。")
    
    # 读取当前配置
    current_rules = engine.rules
    sys_settings = current_rules['system_settings']
    
    with st.form("config_form"):
        new_fuel_rate = st.number_input("FedEx 当周公布燃油费率 (%)", 
                                      value=sys_settings['fuel_surcharge_rate'] * 100, 
                                      step=0.1) / 100
        new_fuel_discount = st.number_input("燃油费折扣 (%)", 
                                          value=sys_settings['fuel_surcharge_discount'] * 100, 
                                          step=1.0) / 100
        new_rebate = st.number_input("信用卡返点率 (%)", 
                                   value=sys_settings['credit_card_rebate_rate'] * 100, 
                                   step=0.1) / 100
        new_dim = st.number_input("抛重系数 (DIM Divisor)", 
                                value=sys_settings['dim_divisor'], 
                                step=1)
        
        submitted = st.form_submit_button("保存配置")
        if submitted:
            # 更新内存中的配置
            sys_settings['fuel_surcharge_rate'] = new_fuel_rate
            sys_settings['fuel_surcharge_discount'] = new_fuel_discount
            sys_settings['credit_card_rebate_rate'] = new_rebate
            sys_settings['dim_divisor'] = new_dim
            
            # 写回 rules.json
            rules_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rules.json')
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(current_rules, f, indent=2, ensure_ascii=False)
            
            # 清除缓存重新加载引擎
            st.cache_resource.clear()
            st.success("配置已更新！")
            st.rerun()

# 主界面：计算器
col1, col2 = st.columns([1.2, 1])

with col1:
    st.markdown('<div class="section-header">📦 货物与物流参数</div>', unsafe_allow_html=True)
    
    with st.container(border=True):
        st.markdown("**1. 尺寸与重量 (Dimensions & Weight)**")
        c1, c2 = st.columns(2)
        with c1:
            actual_weight = st.number_input("实际重量 (lbs) *", min_value=1.0, value=10.0, step=1.0, help="包裹称重实际重量")
        with c2:
            st.markdown("<br>", unsafe_allow_html=True) # 占位对齐
            st.caption("抛重系数: " + str(sys_settings['dim_divisor']))
            
        c3, c4, c5 = st.columns(3)
        with c3:
            length = st.number_input("长 (inch) *", min_value=1.0, value=10.0, step=1.0)
        with c4:
            width = st.number_input("宽 (inch) *", min_value=1.0, value=10.0, step=1.0)
        with c5:
            height = st.number_input("高 (inch) *", min_value=1.0, value=10.0, step=1.0)
            
        st.markdown("---")
        st.markdown("**2. 目的地与服务 (Destination & Services)**")
        c6, c7 = st.columns(2)
        with c6:
            zone = st.number_input("目的地 Zone *", min_value=2, max_value=9, value=5, step=1)
        with c7:
            zip_code = st.text_input("目的邮编 (Zip Code)", placeholder="例如: 1002", help="用于自动判定是否为偏远地区(DAS)")
        
    st.markdown('<div class="section-header">🏷️ 特殊服务与附加选项</div>', unsafe_allow_html=True)
    with st.container(border=True):
        c8, c9 = st.columns(2)
        with c8:
            is_residential = st.checkbox("🏡 住宅地址 (Residential)", value=False)
            is_address_correction = st.checkbox("📍 地址修改/更正", value=False)
        with c9:
            is_irregular = st.checkbox("📦 不规则包装 (AHS-Packaging)", value=False, help="未装入纸箱、圆柱形、外包塑料袋等")
            
        signature_option = st.selectbox(
            "✍️ 签名服务要求",
            options=["不需要 (None)", "Indirect (间接签名)", "Direct (直接签名)", "Adult (成人签名)"]
        )
        # 将选项还原为引擎可识别的格式
        sig_map = {
            "不需要 (None)": None,
            "Indirect (间接签名)": "Indirect",
            "Direct (直接签名)": "Direct",
            "Adult (成人签名)": "Adult"
        }
        engine_sig_opt = sig_map[signature_option]

    st.markdown("<br>", unsafe_allow_html=True)
    calculate_btn = st.button("🚀 执 行 智 能 报 价", type="primary", use_container_width=True)

with col2:
    st.markdown('<div class="section-header">🧾 报价核算回执 (Quotation Receipt)</div>', unsafe_allow_html=True)
    
    if calculate_btn:
        # 构建请求字典
        request_data = {
            "actual_weight": actual_weight,
            "length": length,
            "width": width,
            "height": height,
            "zone": zone,
            "zip_code": zip_code,
            "is_residential": is_residential,
            "is_irregular_packaging": is_irregular,
            "signature_option": engine_sig_opt,
            "is_address_correction": is_address_correction
        }
        
        # 调用引擎计算
        with st.spinner("正在计算最佳报价..."):
            result = engine.calculate_quote(request_data)
            
        if "error" in result:
            st.error(f"⚠️ 计算失败: {result['error']}")
        else:
            # 渲染漂亮的账单
            st.success("✅ 核算完成！数据已同步最新汇率与折扣规则。")
            
            with st.container(border=True):
                st.markdown(f"**⚖️ 计费重量 (Chargeable Weight):** `{result['chargeable_weight']} lbs`")
                st.markdown(f"**🚢 基础运费 (Base Rate):** `${result['base_rate']:.2f}`")
                
                st.markdown("---")
                if result['surcharges']:
                    st.markdown("**🧩 附加费用 (Surcharges):**")
                    for k, v in result['surcharges'].items():
                        st.markdown(f"- {k}: `${v:.2f}`")
                else:
                    st.markdown("**🧩 附加费用:** 无")
                    
                st.markdown(f"**⛽ 燃油附加费 (Fuel Surcharge):** `${result['fuel_surcharge']:.2f}`")
                st.markdown("---")
                st.markdown(f"#### 💳 平台代付账单 (Subtotal): `${result['subtotal']:.2f}`")
                st.markdown(f"💸 信用卡返点抵扣 (Rebate): `- ${result['rebate']:.2f}`")
                
                st.markdown('<div class="highlight-price">💰 最终核算成本: $' + f"{result['final_total']:.2f}" + '</div>', unsafe_allow_html=True)
                
            # 渲染详细计算日志
            st.markdown('<div class="section-header">🔍 智能引擎计算链</div>', unsafe_allow_html=True)
            with st.expander("点击展开查看详细审计日志 (Audit Trail)", expanded=False):
                for log in result['logs']:
                    st.text(log)
    else:
        st.info("👈 请在左侧输入物流参数，点击底部按钮生成智能报价。")
