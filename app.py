import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import io

# ---------------------------------------------------------
# ⚙️ 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="K-Value Oracle V1.3", page_icon="⚖️", layout="wide")

st.title("⚖️ The Quantum Oracle: 한국형 가치투자 분석기 V1.3")
st.markdown("여의도(네이버 금융)의 재무 데이터를 **동적 크롤링 엔진**으로 오차 없이 긁어와 분석합니다.")

# ---------------------------------------------------------
# ⚙️ 사용자 입력 및 네이버 금융 크롤링 엔진
# ---------------------------------------------------------
ticker_input = st.text_input("분석할 한국 주식 종목코드 6자리를 입력하세요 (예: 005930)", "005930")
WACC = st.slider("요구수익률(WACC) 설정 (%) - 통상 8~10% 사용", min_value=5.0, max_value=15.0, value=8.0, step=0.5) / 100

def get_naver_financials(code):
    """네이버 금융에서 실시간 주가 및 기업실적분석(EPS, BPS, ROE) 데이터를 동적으로 안전하게 추출합니다."""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.raise_for_status() # 웹페이지 접속 불량 시 에러 발생
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. 기업명 및 현재가 파싱
        name_tag = soup.select_once('.wrap_company h2 a')
        price_tag = soup.select_once('.no_today .blind')
        
        if not name_tag or not price_tag:
            return {'error': '기업명 또는 현재가를 찾을 수 없습니다. 종목코드를 확인하세요.'}
            
        name = name_tag.text
        current_price = float(price_tag.text.replace(',', ''))
        
        # 2. 기업실적분석 표 동적 파싱 (Pandas 최신버전 대응 io.StringIO 적용)
        dfs = pd.read_html(io.StringIO(res.text), encoding='euc-kr')
        
        target_df = None
        # 몇 번째 표인지 상관없이 '매출액' 항목이 있는 표를 스스로 찾아냅니다.
        for df in dfs:
            if df.iloc[:, 0].astype(str).str.contains('매출액').any():
                target_df = df
                break
                
        if target_df is None:
            return {'error': '재무제표(기업실적분석) 표를 찾을 수 없습니다.'}
            
        # 3. 항목 이름이 포함된 행 인덱스 찾기 (대소문자 무시)
        idx_col = target_df.iloc[:, 0].astype(str)
        eps_idx = idx_col[idx_col.str.contains('EPS', case=False)].index
        bps_idx = idx_col[idx_col.str.contains('BPS', case=False)].index
        roe_idx = idx_col[idx_col.str.contains('ROE', case=False)].index
        
        if len(eps_idx) == 0 or len(bps_idx) == 0 or len(roe_idx) == 0:
            return {'error': 'EPS, BPS, ROE 중 누락된 항목이 있어 계산이 불가능합니다.'}
            
        # 4. 최근 연간 실적 데이터 추출 (컬럼 1~4)
        eps_vals = pd.to_numeric(target_df.iloc[eps_idx[0], 1:5], errors='coerce').dropna()
        bps_vals = pd.to_numeric(target_df.iloc[bps_idx[0], 1:5], errors='coerce').dropna()
        roe_vals = pd.to_numeric(target_df.iloc[roe_idx[0], 1:5], errors='coerce').dropna()
        
        # 최근 값 확정
        eps_latest = eps_vals.iloc[-1] if not eps_vals.empty else 0
        bps_latest = bps_vals.iloc[-1] if not bps_vals.empty else 0
        roe_latest = (roe_vals.iloc[-1] / 100.0) if not roe_vals.empty else 0
        
        eps_history = eps_vals.values
        
        return {
            'name': name,
            'price': current_price,
            'eps': eps_latest,
            'bps': bps_latest,
            'roe': roe_latest,
            'eps_history': eps_history
        }
        
    except Exception as e:
        return {'error': f'시스템 오류 발생: {str(e)}'}

if st.button("🔍 내재 가치 분석 실행"):
    if len(ticker_input) != 6 or not ticker_input.isdigit():
        st.warning("⚠️ 종목코드는 숫자 6자리여야 합니다. (예: 005930)")
        st.stop()
        
    with st.spinner(f"[{ticker_input}] 네이버 금융 재무 데이터 추출 및 4대 엔진 가동 중..."):
        fin_data = get_naver_financials(ticker_input)
        
        # 에러 처리 로직 강화
        if fin_data is None or 'error' in fin_data:
            error_msg = fin_data['error'] if fin_data else '알 수 없는 크롤링 오류'
            st.error(f"❌ 데이터 추출 실패: {error_msg}")
            st.stop()
            
        current_price = fin_data['price']
        eps = fin_data['eps']
        bps = fin_data['bps']
        roe = fin_data['roe']
        eps_history = fin_data['eps_history']
        
        if eps <= 0 or bps <= 0:
            st.error(f"❌ {fin_data['name']}은(는) 현재 적자 기업이거나 자본잠식 상태입니다. (EPS: {eps:,.0f}, BPS: {bps:,.0f}) 보수적 모델은 흑자 기업에만 적용됩니다.")
            st.stop()

        # ---------------------------------------------------------
        # 🧠 4대 보수적 가치평가 엔진
        # ---------------------------------------------------------
        
        # 1. 벤저민 그레이엄 공식
        graham_value = np.sqrt(22.5 * eps * bps)
        
        # 2. 수익력 가치 (EPV)
        epv_value = eps / WACC
        
        # 3. 잔여이익모델 (RIM)
        rim_value = bps + (bps * (roe - WACC) / WACC) if roe > WACC else bps

        # 4. 통계적 보수형 DCF (EPS 성장률 기반 대리 모델)
        dcf_value = 0
        if len(eps_history) >= 3 and all(e > 0 for e in eps_history):
            growth_rates = np.diff(eps_history) / eps_history[:-1]
            mu = np.mean(growth_rates)
            sigma = np.std(growth_rates)
            
            conservative_g = mu - (0.52 * sigma)
            g = max(0.02, min(conservative_g, 0.15)) # 최소 2%, 최대 15% 성장 캡
            
            present_value = 0
            for year in range(1, 6):
                eps_t = eps * ((1 + g) ** year)
                present_value += eps_t / ((1 + WACC) ** year)
            
            tv = (eps * ((1 + g) ** 5) * (1 + 0.025)) / (WACC - 0.025)
            present_value += tv / ((1 + WACC) ** 5)
            dcf_value = present_value
        else:
            dcf_value = epv_value # 과거 적자 기록이 있으면 EPV로 대체

        # ---------------------------------------------------------
        # 📊 결과 종합 및 판별
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
