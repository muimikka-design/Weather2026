import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import urllib3
import re
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="台灣生活氣象與防災儀表板",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================
# 共用 CSS（注入到 Streamlit 頁面）
# =============================================
SHARED_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif !important; }
#MainMenu, footer, header { visibility: hidden; }
.stApp { background: #0f172a !important; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] * { color: #cbd5e1 !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.04) !important;
    border-radius: 14px; padding: 6px; gap: 4px;
    border: 1px solid rgba(255,255,255,0.07);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important; padding: 10px 22px !important;
    color: #94a3b8 !important; font-weight: 500; font-size: 0.9rem;
    transition: all 0.2s ease; border: none !important; background: transparent !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #0ea5e9, #6366f1) !important;
    color: #ffffff !important;
    box-shadow: 0 4px 15px rgba(14,165,233,0.35) !important;
}
.stTabs [data-baseweb="tab-border"] { display: none !important; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 20px; }

/* Streamlit 元件覆蓋 */
.stSelectbox > div > div {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    color: #e2e8f0 !important; border-radius: 10px !important;
}

/* Alert banners via st.markdown */
.alert-banner {
    border-radius: 14px; padding: 14px 20px;
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 20px; font-weight: 500; font-size: 0.9rem;
}
.alert-danger {
    background: linear-gradient(135deg, rgba(239,68,68,0.15), rgba(220,38,38,0.1));
    border: 1px solid rgba(239,68,68,0.35); color: #fca5a5;
}
.alert-safe {
    background: linear-gradient(135deg, rgba(16,185,129,0.12), rgba(5,150,105,0.08));
    border: 1px solid rgba(16,185,129,0.25); color: #6ee7b7;
}
.hero-label { font-size:0.82rem;font-weight:600;text-transform:uppercase;letter-spacing:0.12em;color:rgba(255,255,255,0.6);margin-bottom:8px; }
.section-eyebrow { font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.15em;color:#0ea5e9;margin-bottom:6px; }
.section-title { font-size:1.4rem;font-weight:800;color:#f1f5f9;margin-bottom:20px; }

/* stat cards via st.markdown */
.stat-card {
    background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px; padding: 20px; display: flex; align-items: center; gap: 16px;
}
.stat-icon-ring { width:52px;height:52px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:1.6rem;flex-shrink:0; }
.stat-value { font-size:1.6rem;font-weight:800;color:#f1f5f9;line-height:1;font-variant-numeric:tabular-nums; }
.stat-label { font-size:0.78rem;color:#64748b;margin-top:3px;text-transform:uppercase;letter-spacing:0.06em; }
"""

st.markdown(f"<style>{SHARED_CSS}</style>", unsafe_allow_html=True)


# =============================================
# 用 components.html 渲染的 CSS（standalone）
# =============================================
COMPONENT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap');
* { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Noto Sans TC', sans-serif; }
body { background: transparent; }
"""

# =============================================
# 資料抓取
# =============================================
@st.cache_data(ttl=3600)
def fetch_weather_data():
    url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-C0032-001?Authorization=CWA-5BC80F5C-CB99-4081-94E0-AAD02A6D95C1&downloadType=WEB&format=JSON"
    try:
        r = requests.get(url, verify=False, timeout=10)
        return r.json()['cwaopendata']['dataset']['location']
    except: return []

@st.cache_data(ttl=600)
def fetch_alert_data():
    url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/W-C0033-001?Authorization=CWA-5BC80F5C-CB99-4081-94E0-AAD02A6D95C1&downloadType=WEB&format=JSON"
    try:
        r = requests.get(url, verify=False, timeout=10)
        data = r.json()
        locations = data.get('cwaopendata', {}).get('dataset', {}).get('location', [])
        alerts_dict = {}
        for loc in locations:
            loc_name = loc.get('locationName')
            hazards = loc.get('hazardConditions', {}).get('hazards', [])
            msgs = []
            for h in hazards:
                info = h.get('info', {})
                p, s = info.get('phenomena', ''), info.get('significance', '')
                if p and s: msgs.append(f"{p}{s}")
            alerts_dict[loc_name] = msgs
        return alerts_dict
    except: return {}

@st.cache_data(ttl=600)
def fetch_typhoon_data():
    url = "https://www.dgpa.gov.tw/typh/daily/nds.html"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=10)
        r.encoding = 'utf-8'
        if r.status_code != 200: return None, pd.DataFrame()
        soup = BeautifulSoup(r.text, "html.parser")
        h4 = soup.find("h4")
        update_time = ""
        if h4:
            m = re.search(r"更新時間：\s*\d{4}/\d{2}/\d{2}\s*\d{2}:\d{2}:\d{2}", h4.get_text())
            if m: update_time = m.group(0)
        info_tds = soup.find_all("td", headers="StopWorkSchool_Info")
        if not info_tds: return update_time, pd.DataFrame()
        data = []
        for td in info_tds:
            prev = td.find_previous("td")
            city = prev.get_text(strip=True) if prev else "未知縣市"
            content = td.get_text(strip=True).replace("\xa0", " ")
            data.append({"縣市": city, "公告內容": content})
        return update_time, pd.DataFrame(data)
    except: return None, pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_reservoir_data():
    url = "https://water.taiwanstat.com/data/data.json"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            df = pd.DataFrame(r.json()).T
            df.reset_index(inplace=True)
            df.rename(columns={'index': '水庫名稱'}, inplace=True)
            cols = [c for c in ['水庫名稱', 'percentage', 'volumn', 'updateAt'] if c in df.columns]
            return df[cols]
        return pd.DataFrame()
    except: return pd.DataFrame()


# =============================================
# 輔助函式
# =============================================
def get_weather_icon(pop, wx):
    if "雷" in wx: return "⛈️"
    if pop > 60 or "大雨" in wx or "豪雨" in wx: return "🌧️"
    if pop > 40 or "雨" in wx: return "🌦️"
    if "多雲" in wx: return "⛅"
    if "陰" in wx: return "🌥️"
    return "☀️"

def get_hero_bg(pop, wx):
    if pop > 40 or "雨" in wx:
        return "linear-gradient(135deg,#0f1729 0%,#1e3a5f 50%,#1e40af 100%)"
    if "雲" in wx or "陰" in wx:
        return "linear-gradient(135deg,#1e293b 0%,#334155 50%,#475569 100%)"
    return "linear-gradient(135deg,#1e3a5f 0%,#0369a1 50%,#0284c7 100%)"

def get_pop_gradient(pop):
    if pop > 60: return "linear-gradient(90deg,#6366f1,#818cf8)"
    if pop > 30: return "linear-gradient(90deg,#0ea5e9,#38bdf8)"
    return "linear-gradient(90deg,#10b981,#34d399)"

def get_pop_color(pop):
    if pop > 60: return "#818cf8"
    if pop > 30: return "#38bdf8"
    return "#34d399"

def get_reservoir_colors(pct):
    try:
        v = float(pct)
        if v >= 80: return "#10b981", "#34d399"
        if v >= 50: return "#0ea5e9", "#38bdf8"
        if v >= 25: return "#f59e0b", "#fbbf24"
        return "#ef4444", "#f87171"
    except: return "#64748b", "#94a3b8"

def make_ring_svg(pct_num, uid):
    pct = max(0, min(100, float(pct_num) if pct_num else 0))
    r = 32
    circ = 2 * 3.14159 * r
    offset = circ * (1 - pct / 100)
    c1, c2 = get_reservoir_colors(pct)
    return f"""<svg width="80" height="80" viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="rg{uid}" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <circle cx="40" cy="40" r="{r}" fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="8"/>
  <circle cx="40" cy="40" r="{r}" fill="none"
    stroke="url(#rg{uid})" stroke-width="8" stroke-linecap="round"
    stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"
    transform="rotate(-90 40 40)"/>
</svg>""", c1


# =============================================
# 載入資料
# =============================================
weather_data = fetch_weather_data()
alert_data   = fetch_alert_data()
closure_time, closure_df = fetch_typhoon_data()
reservoir_df = fetch_reservoir_data()

if not weather_data:
    st.error("氣象資料載入失敗，請稍後再試。")
    st.stop()


# =============================================
# 側邊欄
# =============================================
with st.sidebar:
    st.markdown("""
    <div style="padding:12px 0 20px;">
      <div style="font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.15em;color:#475569;margin-bottom:6px;">系統設定</div>
      <div style="font-size:1.1rem;font-weight:800;color:#f1f5f9;">儀表板控制台</div>
    </div>""", unsafe_allow_html=True)

    selected_loc = st.selectbox("查詢縣市", [loc['locationName'] for loc in weather_data])

    st.markdown("<hr style='border-color:rgba(255,255,255,0.06);margin:20px 0;'>", unsafe_allow_html=True)
    for emoji, title, src in [
        ("🌐", "中央氣象署", "天氣預報 & 特報"),
        ("📋", "人事行政總處", "停班停課公告"),
        ("💧", "台灣水庫水情", "即時蓄水資料"),
    ]:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
          <div style="font-size:1.1rem;">{emoji}</div>
          <div>
            <div style="font-size:0.82rem;font-weight:600;color:#94a3b8;">{title}</div>
            <div style="font-size:0.72rem;color:#475569;">{src}</div>
          </div>
        </div>""", unsafe_allow_html=True)


# =============================================
# 頁首橫幅
# =============================================
st.markdown("""
<div style="position:relative;overflow:hidden;border-radius:24px;margin-bottom:24px;
  background:linear-gradient(135deg,#0c1445 0%,#1a237e 40%,#0d47a1 100%);
  padding:36px 40px;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
  <div style="position:absolute;inset:0;background-image:
    radial-gradient(1.5px 1.5px at 15% 20%,rgba(255,255,255,0.8) 0%,transparent 100%),
    radial-gradient(1px 1px at 32% 55%,rgba(255,255,255,0.5) 0%,transparent 100%),
    radial-gradient(2px 2px at 55% 12%,rgba(255,255,255,0.6) 0%,transparent 100%),
    radial-gradient(1px 1px at 72% 38%,rgba(255,255,255,0.4) 0%,transparent 100%),
    radial-gradient(1.5px 1.5px at 88% 65%,rgba(255,255,255,0.7) 0%,transparent 100%),
    radial-gradient(1px 1px at 6% 80%,rgba(255,255,255,0.5) 0%,transparent 100%);
    pointer-events:none;"></div>
  <div style="position:relative;z-index:2;display:flex;align-items:center;gap:20px;">
    <div style="width:72px;height:72px;border-radius:50%;background:rgba(255,255,255,0.12);
      border:2px solid rgba(255,255,255,0.2);display:flex;align-items:center;justify-content:center;
      font-size:2.2rem;box-shadow:0 0 30px rgba(56,189,248,0.3);flex-shrink:0;">🌏</div>
    <div>
      <div style="color:#fff;font-size:1.9rem;font-weight:900;letter-spacing:-0.02em;text-shadow:0 2px 20px rgba(0,0,0,0.3);">
        台灣生活氣象與防災儀表板</div>
      <div style="color:rgba(255,255,255,0.65);font-size:0.88rem;margin-top:4px;letter-spacing:0.05em;">
        TAIWAN WEATHER &amp; DISASTER PREVENTION DASHBOARD</div>
    </div>
    <div style="margin-left:auto;background:rgba(16,185,129,0.2);border:1px solid rgba(16,185,129,0.4);
      color:#34d399;padding:6px 16px;border-radius:100px;font-size:0.78rem;font-weight:600;
      letter-spacing:0.05em;white-space:nowrap;">🟢 即時資料</div>
  </div>
</div>""", unsafe_allow_html=True)


# =============================================
# 分頁
# =============================================
tab1, tab2, tab3 = st.tabs(["🌤️　氣象預報與特報", "📢　停班停課公告", "💧　水庫水情查詢"])


# ─────────────────────────────────────────────
# 分頁 1：氣象預報
# ─────────────────────────────────────────────
with tab1:
    target_loc = next(loc for loc in weather_data if loc['locationName'] == selected_loc)
    dd = {"MinT": [], "MaxT": [], "PoP": [], "Wx": [], "time_short": []}
    for elem in target_loc['weatherElement']:
        n = elem['elementName']
        if n == "MinT":   dd["MinT"] = [int(t['parameter']['parameterName']) for t in elem['time']]
        elif n == "MaxT": dd["MaxT"] = [int(t['parameter']['parameterName']) for t in elem['time']]
        elif n == "PoP":  dd["PoP"]  = [int(t['parameter']['parameterName']) for t in elem['time']]
        elif n == "Wx":
            dd["Wx"] = [t['parameter']['parameterName'] for t in elem['time']]
            dd["time_short"] = [t['startTime'][5:10] for t in elem['time']]

    icons   = [get_weather_icon(dd["PoP"][i], dd["Wx"][i]) for i in range(3)]
    hero_bg = get_hero_bg(dd["PoP"][0], dd["Wx"][0])
    avg_temp = (dd["MinT"][0] + dd["MaxT"][0]) // 2

    # 警報橫幅
    alerts = alert_data.get(selected_loc, [])
    if alerts:
        st.markdown(f"""<div class="alert-banner alert-danger">
          <span style="font-size:1.4rem;">🚨</span>
          <span><strong>天氣警特報</strong>｜{selected_loc} 目前發布：<strong>{"、".join(alerts)}</strong>，請多加留意</span>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div class="alert-banner alert-safe">
          <span style="font-size:1.3rem;">✅</span>
          <span><strong>{selected_loc}</strong> 目前無重大天氣警特報，天氣狀況良好</span>
        </div>""", unsafe_allow_html=True)

    # 英雄卡 + 降雨圖 (用 components.html 渲染)
    col_hero, col_chart = st.columns([7, 3])

    with col_hero:
        pop0 = dd["PoP"][0]
        hero_html = f"""{COMPONENT_CSS}
.hero {{ position:relative;overflow:hidden;border-radius:24px;padding:36px 40px;
  background:{hero_bg};display:flex;align-items:center;justify-content:space-between;
  box-shadow:0 20px 50px rgba(0,0,0,0.4); }}
.hero::before {{ content:'';position:absolute;right:-30px;top:-30px;width:240px;height:240px;
  border-radius:50%;background:rgba(255,255,255,0.04);pointer-events:none; }}
.label {{ font-size:0.82rem;font-weight:600;text-transform:uppercase;letter-spacing:0.12em;
  color:rgba(255,255,255,0.6);margin-bottom:8px; }}
.temp {{ font-size:5.5rem;font-weight:900;color:#fff;line-height:1;letter-spacing:-0.04em;
  text-shadow:0 4px 30px rgba(0,0,0,0.3); }}
.unit {{ font-size:2rem;font-weight:300;opacity:.7;vertical-align:super; }}
.wx {{ font-size:1.25rem;color:rgba(255,255,255,0.85);font-weight:500;margin-top:8px; }}
.meta {{ display:flex;gap:16px;margin-top:14px; }}
.pill {{ background:rgba(255,255,255,0.12);backdrop-filter:blur(8px);
  border:1px solid rgba(255,255,255,0.15);color:rgba(255,255,255,0.9);
  padding:5px 14px;border-radius:100px;font-size:0.82rem;font-weight:500; }}
.big-icon {{ font-size:7rem;line-height:1;filter:drop-shadow(0 8px 24px rgba(0,0,0,0.3));
  animation:float 4s ease-in-out infinite; }}
@keyframes float {{ 0%,100% {{ transform:translateY(0); }} 50% {{ transform:translateY(-12px); }} }}
</style>
<div class="hero">
  <div>
    <div class="label">📍 {selected_loc}　今日天氣</div>
    <div class="temp">{avg_temp}<span class="unit">°C</span></div>
    <div class="wx">{dd['Wx'][0]}</div>
    <div class="meta">
      <div class="pill">🌡️ {dd['MinT'][0]}° – {dd['MaxT'][0]}°</div>
      <div class="pill">🌧️ 降雨 {pop0}%</div>
    </div>
  </div>
  <div class="big-icon">{icons[0]}</div>
</div>"""
        components.html(hero_html, height=210)

    with col_chart:
        pop_rows = ""
        for i in range(3):
            p = dd["PoP"][i]
            d = dd["time_short"][i] if dd["time_short"] else ""
            g = get_pop_gradient(p)
            pop_rows += f"""
            <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
              <div style="font-size:0.78rem;color:#94a3b8;width:52px;text-align:right;flex-shrink:0;">{d}</div>
              <div style="flex:1;height:10px;background:rgba(255,255,255,0.06);border-radius:100px;overflow:hidden;">
                <div style="width:{p}%;height:100%;background:{g};border-radius:100px;"></div>
              </div>
              <div style="font-size:0.82rem;font-weight:700;width:36px;color:#e2e8f0;">{p}%</div>
            </div>"""

        chart_html = f"""{COMPONENT_CSS}
body {{ background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);
  border-radius:18px;padding:24px; }}
.title {{ font-size:0.75rem;font-weight:700;text-transform:uppercase;
  letter-spacing:0.1em;color:#64748b;margin-bottom:20px; }}
.foot {{ margin-top:16px;padding-top:14px;border-top:1px solid rgba(255,255,255,0.05);
  font-size:0.68rem;color:#475569;text-align:center; }}
</style>
<div class="title">☔ 36 小時降雨機率</div>
{pop_rows}
<div class="foot">每 12 小時為一預報時段</div>"""
        components.html(chart_html, height=210)

    # 三時段預報子卡
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    time_labels = ["今日白天", "今晚明晨", "明日白天"]
    cols_bottom = st.columns(3)
    for i in range(3):
        with cols_bottom[i]:
            p = dd["PoP"][i]
            g = get_pop_gradient(p)
            c = get_pop_color(p)
            d = dd["time_short"][i] if dd["time_short"] else ""
            card_html = f"""{COMPONENT_CSS}
body {{ background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);
  border-radius:18px;padding:22px 16px;text-align:center;
  transition:all 0.25s ease; }}
.lbl {{ font-size:0.75rem;font-weight:700;text-transform:uppercase;
  letter-spacing:0.1em;color:#64748b;margin-bottom:10px; }}
.date {{ font-size:0.85rem;color:#94a3b8;margin-bottom:10px; }}
.icon {{ font-size:2.8rem;margin:8px 0;line-height:1.2; }}
.temps {{ font-size:1.35rem;font-weight:800;color:#e2e8f0;margin:8px 0;
  font-variant-numeric:tabular-nums; }}
.wx {{ font-size:0.82rem;color:#94a3b8;margin-bottom:10px; }}
.bar-label {{ font-size:0.72rem;color:#64748b;text-transform:uppercase;
  letter-spacing:0.08em;margin-bottom:5px; }}
.bar-track {{ width:100%;height:6px;background:rgba(255,255,255,0.08);
  border-radius:100px;overflow:hidden;margin-bottom:6px; }}
.bar-fill {{ height:100%;border-radius:100px; }}
.pop-val {{ font-size:1.1rem;font-weight:700;font-variant-numeric:tabular-nums; }}
</style>
<div class="lbl">{time_labels[i]}</div>
<div class="date">📅 {d}</div>
<div class="icon">{icons[i]}</div>
<div class="temps">{dd['MinT'][i]}° – {dd['MaxT'][i]}°C</div>
<div class="wx">{dd['Wx'][i]}</div>
<div class="bar-label">☔ 降雨機率</div>
<div class="bar-track"><div class="bar-fill" style="width:{p}%;background:{g};"></div></div>
<div class="pop-val" style="color:{c};">{p}%</div>"""
            components.html(card_html, height=280)


# ─────────────────────────────────────────────
# 分頁 2：停班停課
# ─────────────────────────────────────────────
with tab2:
    st.markdown("""
    <div class="section-eyebrow">TYPHOON RESPONSE</div>
    <div class="section-title">📢 停班停課公告</div>
    """, unsafe_allow_html=True)

    if closure_time:
        st.markdown(f"""
        <div style="display:inline-flex;align-items:center;gap:8px;
          background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);
          border-radius:10px;padding:8px 16px;margin-bottom:20px;">
          <span style="font-size:0.75rem;color:#64748b;">🕒 資料更新時間</span>
          <span style="font-size:0.82rem;font-weight:600;color:#94a3b8;">{closure_time}</span>
        </div>""", unsafe_allow_html=True)

    if not closure_df.empty:
        rows_html = ""
        for _, row in closure_df.iterrows():
            city    = str(row.get('縣市', '')).replace('<', '&lt;').replace('>', '&gt;')
            content = str(row.get('公告內容', '')).replace('<', '&lt;').replace('>', '&gt;')
            rows_html += f"""
            <div class="row">
              <div class="city">📍 {city}</div>
              <div class="content">{content}</div>
            </div>"""

        table_html = f"""{COMPONENT_CSS}
body {{ background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);
  border-radius:18px;overflow:hidden; }}
.header {{ display:grid;grid-template-columns:140px 1fr;
  background:rgba(255,255,255,0.04);border-bottom:1px solid rgba(255,255,255,0.08); }}
.header-cell {{ padding:10px 20px;font-size:0.72rem;font-weight:700;
  text-transform:uppercase;letter-spacing:0.1em;color:#475569; }}
.row {{ display:grid;grid-template-columns:140px 1fr;
  border-bottom:1px solid rgba(255,255,255,0.05); }}
.row:last-child {{ border-bottom:none; }}
.city {{ padding:14px 20px;font-size:0.88rem;font-weight:600;color:#94a3b8;
  border-right:1px solid rgba(255,255,255,0.05);display:flex;align-items:center;gap:8px; }}
.content {{ padding:14px 20px;font-size:0.85rem;color:#cbd5e1;display:flex;align-items:center; }}
</style>
<div class="header">
  <div class="header-cell">縣市</div>
  <div class="header-cell">公告內容</div>
</div>
{rows_html}"""

        row_count = len(closure_df)
        height = max(200, row_count * 50 + 50)
        components.html(table_html, height=height, scrolling=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
          <div style="font-size:4rem;margin-bottom:16px;">✅</div>
          <div style="font-size:1.2rem;font-weight:700;color:#34d399;margin-bottom:8px;">目前無停班停課公告</div>
          <div style="font-size:0.88rem;color:#64748b;">全台各縣市皆維持正常上班上課</div>
        </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 分頁 3：水庫水情
# ─────────────────────────────────────────────
with tab3:
    st.markdown("""
    <div class="section-eyebrow">RESERVOIR STATUS</div>
    <div class="section-title">💧 全台水庫即時水情</div>
    """, unsafe_allow_html=True)

    if not reservoir_df.empty:
        try:
            numeric_pcts = pd.to_numeric(reservoir_df['percentage'], errors='coerce').dropna()
            avg_pct      = numeric_pcts.mean()
            low_count    = int((numeric_pcts < 30).sum())
            healthy_count = int((numeric_pcts >= 60).sum())
        except:
            avg_pct = 0; low_count = 0; healthy_count = 0

        color_avg = "#34d399" if avg_pct >= 60 else "#fbbf24" if avg_pct >= 30 else "#f87171"
        c1, c2, c3, c4 = st.columns(4)
        for col, icon, val, label, color, bg in [
            (c1, "💧", str(len(reservoir_df)), "監測水庫數", "#f1f5f9", "rgba(14,165,233,0.12)"),
            (c2, "📊", f"{avg_pct:.1f}%", "平均蓄水率", color_avg, "rgba(16,185,129,0.12)"),
            (c3, "⚠️", str(low_count), "低水位水庫 (<30%)", "#f87171", "rgba(239,68,68,0.12)"),
            (c4, "✅", str(healthy_count), "充足水庫 (≥60%)", "#34d399", "rgba(16,185,129,0.1)"),
        ]:
            with col:
                col.markdown(f"""
                <div class="stat-card">
                  <div class="stat-icon-ring" style="background:{bg};">{icon}</div>
                  <div>
                    <div class="stat-value" style="color:{color};">{val}</div>
                    <div class="stat-label">{label}</div>
                  </div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px;">
          <div style="display:flex;align-items:center;gap:6px;font-size:0.75rem;color:#94a3b8;">
            <div style="width:12px;height:12px;border-radius:3px;background:#10b981;"></div> ≥ 80% 充裕</div>
          <div style="display:flex;align-items:center;gap:6px;font-size:0.75rem;color:#94a3b8;">
            <div style="width:12px;height:12px;border-radius:3px;background:#0ea5e9;"></div> 50–79% 正常</div>
          <div style="display:flex;align-items:center;gap:6px;font-size:0.75rem;color:#94a3b8;">
            <div style="width:12px;height:12px;border-radius:3px;background:#f59e0b;"></div> 25–49% 偏低</div>
          <div style="display:flex;align-items:center;gap:6px;font-size:0.75rem;color:#94a3b8;">
            <div style="width:12px;height:12px;border-radius:3px;background:#ef4444;"></div> &lt; 25% 警戒</div>
        </div>""", unsafe_allow_html=True)

        # 水庫卡片：每行4欄，用 columns 渲染，components.html 給 SVG 圓環
        rows = list(reservoir_df.iterrows())
        cols_per_row = 4
        for row_start in range(0, len(rows), cols_per_row):
            chunk = rows[row_start: row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for col_idx, (_, row) in enumerate(chunk):
                name    = str(row.get('水庫名稱', ''))
                pct_raw = row.get('percentage', 0)
                vol     = row.get('volumn', 'N/A')
                updated = str(row.get('updateAt', ''))[:10]
                try:
                    pct_num = float(pct_raw)
                    pct_display = f"{pct_num:.1f}%"
                except:
                    pct_num = 0; pct_display = "N/A"

                uid = f"{row_start}_{col_idx}"
                svg_str, ring_color = make_ring_svg(pct_num, uid)

                card_html = f"""{COMPONENT_CSS}
body {{ background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);
  border-radius:16px;padding:20px 16px;text-align:center; }}
.name {{ font-size:0.9rem;font-weight:700;color:#e2e8f0;margin-bottom:14px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis; }}
.ring-wrap {{ position:relative;width:80px;height:80px;margin:0 auto 14px; }}
.ring-wrap svg {{ display:block; }}
.pct-text {{ position:absolute;inset:0;display:flex;align-items:center;
  justify-content:center;font-size:1.1rem;font-weight:900;
  font-variant-numeric:tabular-nums; }}
.vol {{ font-size:0.72rem;color:#64748b;line-height:1.4; }}
.vol strong {{ color:#e2e8f0; }}
.updated {{ font-size:0.68rem;color:#475569;margin-top:4px; }}
</style>
<div class="name">💧 {name}</div>
<div class="ring-wrap">
  {svg_str}
  <div class="pct-text" style="color:{ring_color};">{pct_display}</div>
</div>
<div class="vol">蓄水量<br><strong>{vol}</strong> 萬m³</div>
<div class="updated">更新：{updated}</div>"""

                with cols[col_idx]:
                    components.html(card_html, height=200)
    else:
        st.markdown("""
        <div style="text-align:center;padding:60px 20px;">
          <div style="font-size:4rem;margin-bottom:16px;">⚠️</div>
          <div style="font-size:1.1rem;font-weight:700;color:#f87171;">無法載入水庫資料</div>
          <div style="font-size:0.85rem;color:#64748b;margin-top:6px;">請稍後再試或確認網路連線</div>
        </div>""", unsafe_allow_html=True)
