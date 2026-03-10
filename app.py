import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import io

# ---------------------------------------------------------
# ⚙️ 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="K-Value Oracle V1.5", page_icon="⚖️", layout="wide")

st.title("⚖️ The Quantum Oracle: 한국형 가치투자 분석기 V1.5")
st.markdown("여의도(네이버 금융)의 재무 데이터를 **4단계 정밀 크롤링 엔진**으로 오차 없이 긁어와 분석합니다.")

# ---------------------------------------------------------
# ⚙️ 사용자 입력
# ---------------------------------------------------------
ticker_input = st.text_input("분석할 한국 주식 종목코드 6자리를 입력하세요 (예: 005930)", "005930")
WACC = st.slider("요구수익률(WACC) 설정 (%) - 통상 8~10% 사용", min_value=5.0, max_value=15.0, value=8.0, step=0.5) / 100

# ---------------------------------------------------------
# 🕷️ 4단계 정밀 크롤링 엔진 (한글 인코딩 완벽 패치)
# ---------------------------------------------------------
def get_naver_financials(code):
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status() 
        
        # 🌟 인코딩 패치: 텍스트 대신 순수 바이트(content)를 가져와서 euc-kr로 강제 디코딩
        html_text = res.content.decode('euc-kr', 'replace')
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # [Step 2] 기업명 및 현재가 정밀 추출
        name_area = soup.find('div', {'class': 'wrap_company'})
        if name_area is None: return {'error': '[크롤링 1단계] 기업명 영역을 찾을 수 없습니다.'}
        
        name_tag = name_area.find('h2')
        if name_tag is None: return {'error': '[크롤링 1단계] 기업명 텍스트를 찾을 수 없습니다.'}
        name = name_tag.find('a').text
        
        price_area = soup.find('p', {'class': 'no_today'})
        if price_area is None: return {'error': '[크롤링 1단계] 현재가 영역을 찾을 수 없습니다.'}
        
        price_tag = price_area.find('span', {'class': 'blind'})
        if price_tag is None: return {'error': '[크롤링 1단계] 현재가 숫자를 찾을 수 없습니다.'}
        current_price = float(price_tag.text.replace(',', ''))
        
        # [Step 3] 기업실적분석 표(Table) 영역만 도려내기
        cop_analysis = soup.find('div', {'class': 'cop_analysis'})
        if cop_analysis is None: return {'error': '[크롤링 2단계] 기업실적분석 표를 찾을 수 없습니다.'}
        
        table_html = str(cop_analysis.find('table'))
        dfs = pd.read_html(io.StringIO(table_html))
        
        if not dfs: return {'error': '[크롤링 3단계] 추출한 표를 판다스로 읽어들이지 못했습니다.'}
        df = dfs[0]
        
        # [Step 4] 다중 인덱스 붕괴 및 목표 데이터 스캔
        df.columns = range(df.shape[1]) 
        idx_col = df[0].astype(str) 
        
        eps_row = df[idx_col.str.contains('EPS', na=False, case=False)]
        bps_row = df[idx_col.str.contains('BPS', na=False, case=False)]
        roe_row = df[idx_col.str.contains('ROE', na=False, case=False)]
        
        if eps_row.empty or bps_row.empty or roe_row.empty:
            return {'error': '[크롤링 4단계] 표 내부에 EPS, BPS, ROE 중 누락된 항목이 있습니다.'}
            
        eps_vals = pd.to_numeric(eps_row.iloc[0, 1:5], errors='coerce').dropna()
        bps_vals = pd.to_numeric(bps_row.iloc[0, 1:5], errors='coerce').dropna()
        roe_vals = pd.to_numeric(roe_row.iloc[0, 1:5], errors='coerce').dropna()
        
        eps_latest = eps_vals.iloc[-1] if not eps_vals.empty else 0
        bps_latest = bps_vals.iloc[-1] if not bps_vals.empty else 0
        roe_latest = (roe_vals.iloc[-1] / 100.0) if not roe_vals.empty else 0
        
        return {
            'name': name,
            'price': current_price,
            'eps': eps_latest,
            'bps': bps_latest,
            'roe': roe_latest,
            'eps_history': eps_vals.values
        }
        
    except Exception as e:
        return {'error': f'[시스템 오류] {str(e)}'}

# ---------------------------------------------------------
# 🚀 메인 실행 로직
# ---------------------------------------------------------
if st.button("🔍 내재 가치 분석 실행"):
    if len(ticker_input) != 6 or not ticker_input.isdigit():
        st.warning("⚠️ 종목코드는 숫자 6자리여야 합니다. (예: 005930)")
        st.stop()
        
    with st.spinner(f"[{ticker_input}] 정밀 크롤링 엔진 가동 중..."):
        fin_data = get_naver_financials(ticker_input)
        
        if 'error' in fin_data:
            st.error(f"❌ 데이터 추출 실패: {fin_data['error']}")
            st.stop()
            
        current_price = fin_data['price']
        eps = fin_data['eps']
        bps = fin_data['bps']
        roe = fin_data['roe']
        eps_history = fin_data['eps_history']
        
        if eps <= 0 or bps <= 0:
            st.error(f"❌ {fin_data['name']}은(는) 현재 적자 기업이거나 자본잠식 상태입니다. (EPS: {eps:,.0f}, BPS: {bps:,.0f})\n보수적 가치평가 모델은 흑자 기업에만 적용됩니다.")
            st.stop()

        # ---------------------------------------------------------
        # 🧠 4대 보수적 가치평가 엔진 산출
        # ---------------------------------------------------------
        graham_value = np.sqrt(22.5 * eps * bps)
        epv_value = eps / WACC
        rim_value = bps + (bps * (roe - WACC) / WACC) if roe > WACC else bps

        dcf_value = 0
        if len(eps_history) >= 3 and all(e > 0 for e in eps_history):
            growth_rates = np.diff(eps_history) / eps_history[:-1]
            mu = np.mean(growth_rates)
            sigma = np.std(growth_rates)
            
            conservative_g = mu - (0.52 * sigma)
            g = max(0.02, min(conservative_g, 0.15)) 
            
            present_value = 0
            for year in range(1, 6):
                eps_t = eps * ((1 + g) ** year)
                present_value += eps_t / ((1 + WACC) ** year)
            
            tv = (eps * ((1 + g) ** 5) * (1 + 0.025)) / (WACC - 0.025)
            present_value += tv / ((1 + WACC) ** 5)
            dcf_value = present_value
        else:
            dcf_value = epv_value

        # ---------------------------------------------------------
        # 📊 결과 렌더링
        # ---------------------------------------------------------
        models = {'Graham': graham_value, 'EPV': epv_value, 'RIM': rim_value, 'Stat-DCF': dcf_value}
        strict_fair_value = min(models.values())
        
        st.subheader(f"📊 {fin_data['name']} ({ticker_input}) 가치 평가 결과")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("현재 주가", f"₩{current_price:,.0f}")
        col2.metric("가장 보수적인 적정 주가", f"₩{strict_fair_value:,.0f}")
        
        margin_of_safety = ((strict_fair_value - current_price) / strict_fair_value) * 100
        col3.metric("안전 마진 (Margin of Safety)", f"{margin_of_safety:,.1f}%")
        
        if current_price < strict_fair_value:
            col4.success("🟢 STRONG BUY (저평가)")
        elif current_price < strict_fair_value * 1.1: 
            col4.warning("🟡 HOLD (적정 가치)")
        else:
            col4.error("🔴 SELL (고평가)")

        st.markdown("---")
        st.markdown("### ⚙️ 4대 엔진 개별 산출가")
        
        st.info(f"**1. 그레이엄 내재가치 (Graham):** ₩{graham_value:,.0f} \n\n (성장 배제. EPS와 BPS만을 이용한 전통적 가치)")
        st.info(f"**2. 잔여이익모델 (RIM):** ₩{rim_value:,.0f} \n\n (요구수익률 초과 이익 가치화. 버핏의 선호 방식)")
        st.info(f"**3. 수익력 가치 (EPV):** ₩{epv_value:,.0f} \n\n (미래 성장률 0%로 가정한 가장 가혹한 모델)")
        st.info(f"**4. 통계적 보수형 DCF:** ₩{dcf_value:,.0f} \n\n (과거 변동성 기반 '하위 30%' 보수적 성장률 적용)")

st.markdown("---")
st.caption("Data Source: Naver Finance | 본 대시보드는 재무제표 기반의 기계적/보수적 가치 평가를 수행합니다.")
