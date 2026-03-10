import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# ⚙️ 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="K-Value Oracle V1.1", page_icon="⚖️", layout="wide")

st.title("⚖️ The Quantum Oracle: 한국형 가치투자 분석기 V1.1")
st.markdown("워런 버핏의 내재가치와 퀀트 통계학을 결합한 **극강의 보수적 가치 평가 엔진 (KOSPI/KOSDAQ 전용)**입니다.")

# ---------------------------------------------------------
# ⚙️ 사용자 입력 및 티커 탐색 로직
# ---------------------------------------------------------
ticker_input = st.text_input("분석할 한국 주식 종목코드 6자리를 입력하세요 (예: 005930)", "005930")
WACC = st.slider("요구수익률(WACC) 설정 (%) - 통상 8~10% 사용", min_value=5.0, max_value=15.0, value=8.0, step=0.5) / 100

def get_korean_ticker(code):
    """숫자 6자리 코드를 받아 코스피(.KS) 또는 코스닥(.KQ) 티커를 반환합니다."""
    if len(code) != 6 or not code.isdigit():
        return None
    
    # 1. 코스피 먼저 시도
    ks_ticker = f"{code}.KS"
    stock = yf.Ticker(ks_ticker)
    # 현재가 정보가 존재하면 코스피 종목으로 간주
    if stock.info.get('currentPrice', None) is not None or stock.info.get('regularMarketPrice', None) is not None:
        return ks_ticker
        
    # 2. 코스피에 없으면 코스닥 시도
    kq_ticker = f"{code}.KQ"
    stock = yf.Ticker(kq_ticker)
    if stock.info.get('currentPrice', None) is not None or stock.info.get('regularMarketPrice', None) is not None:
        return kq_ticker
        
    return None

if st.button("🔍 내재 가치 분석 실행"):
    with st.spinner(f"[{ticker_input}] 여의도 재무 데이터 추출 및 4대 엔진 가동 중..."):
        valid_ticker = get_korean_ticker(ticker_input)
        
        if not valid_ticker:
            st.error("❌ 유효하지 않은 종목코드이거나 상장폐지된 종목입니다. 숫자 6자리를 정확히 입력해주세요.")
            st.stop()
            
        try:
            # 1. 데이터 수집
            stock = yf.Ticker(valid_ticker)
            info = stock.info
            cashflow = stock.cashflow
            
            # 기초 데이터 파싱 (한국 시장은 원화 기준)
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            eps = info.get('trailingEps', 0)
            bps = info.get('bookValue', 0)
            roe = info.get('returnOnEquity', 0)
            
            if current_price == 0 or eps <= 0 or bps <= 0:
                st.error("❌ 적자 기업이거나 야후 파이낸스 서버에 재무 데이터가 누락되어 있습니다. (보수적 모델은 흑자 기업에만 적용 가능합니다)")
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

            # 4. 통계적 보수형 DCF
            dcf_value = 0
            if 'Free Cash Flow' in cashflow.index:
                fcf_history = cashflow.loc['Free Cash Flow'].dropna().values[::-1] 
                if len(fcf_history) >= 3 and all(f > 0 for f in fcf_history):
                    growth_rates = np.diff(fcf_history) / fcf_history[:-1]
                    mu = np.mean(growth_rates)
                    sigma = np.std(growth_rates)
                    conservative_g = mu - (0.52 * sigma)
                    g = max(0.02, min(conservative_g, 0.15))
                    
                    fcf_0 = fcf_history[-1] / info.get('sharesOutstanding', 1) 
                    present_value = 0
                    for year in range(1, 6):
                        fcf_t = fcf_0 * ((1 + g) ** year)
                        present_value += fcf_t / ((1 + WACC) ** year)
                    
                    tv = (fcf_0 * ((1 + g) ** 5) * (1 + 0.025)) / (WACC - 0.025)
                    present_value += tv / ((1 + WACC) ** 5)
                    dcf_value = present_value
                else:
                    dcf_value = epv_value 
            else:
                dcf_value = epv_value # 현금흐름 누락 시 EPV 대체

            # ---------------------------------------------------------
            # 📊 결과 종합 및 판별
            # ---------------------------------------------------------
            models = {'Graham': graham_value, 'EPV': epv_value, 'RIM': rim_value, 'Stat-DCF': dcf_value}
            strict_fair_value = min(models.values())
            
            st.subheader(f"📊 {info.get('shortName', ticker_input)} ({valid_ticker}) 가치 평가 결과")
            
            col1, col2, col3, col4 = st.columns(4)
            # 한국 주식은 소수점 없이 원화(₩) 단위로 표시
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
            
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다. (Error: {e})")

st.markdown("---")
st.caption("주의: 본 대시보드는 재무제표 기반의 기계적/보수적 가치 평가를 수행하며, 테마주/작전주 분석에는 적합하지 않습니다. 야후 파이낸스 데이터 누락 시 분석이 제한될 수 있습니다.")
