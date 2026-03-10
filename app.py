import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# ⚙️ 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="Value Investing Oracle V1.0", page_icon="⚖️", layout="wide")

st.title("⚖️ The Quantum Oracle: 가치투자 자동 분석기 V1.0")
st.markdown("워런 버핏의 내재가치와 퀀트의 통계학을 결합한 **극강의 보수적 가치 평가 엔진**입니다.")

# ---------------------------------------------------------
# ⚙️ 사용자 입력
# ---------------------------------------------------------
ticker_input = st.text_input("분석할 미국 주식 티커를 입력하세요 (예: AAPL, MSFT, NVDA)", "AAPL")
WACC = st.slider("요구수익률(WACC) 설정 (%) - 통상 8~10% 사용", min_value=5.0, max_value=15.0, value=8.0, step=0.5) / 100

if st.button("🔍 내재 가치 분석 실행"):
    with st.spinner(f"[{ticker_input}] 월스트리트 재무 데이터 추출 및 4대 엔진 가동 중..."):
        try:
            # 1. 데이터 수집 (yfinance)
            stock = yf.Ticker(ticker_input)
            info = stock.info
            financials = stock.financials
            cashflow = stock.cashflow
            
            # 기초 데이터 파싱
            current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            eps = info.get('trailingEps', 0)
            bps = info.get('bookValue', 0)
            roe = info.get('returnOnEquity', 0)
            
            if current_price == 0 or eps <= 0 or bps <= 0:
                st.error("❌ 적자 기업이거나 재무 데이터를 정상적으로 불러올 수 없습니다. (보수적 모델은 흑자 기업에만 적용 가능합니다)")
                st.stop()

            # ---------------------------------------------------------
            # 🧠 4대 보수적 가치평가 엔진
            # ---------------------------------------------------------
            
            # 1. 벤저민 그레이엄 공식 (성장 배제, 자산/이익 중심)
            # V = sqrt(22.5 * EPS * BPS)
            graham_value = np.sqrt(22.5 * eps * bps)
            
            # 2. 수익력 가치 (EPV) (미래 성장률 0% 극단적 가정)
            # V = EPS / WACC (간이 조정 이익 사용)
            epv_value = eps / WACC
            
            # 3. 잔여이익모델 (RIM) (초과 이익 기반)
            # V = BPS + BPS * (ROE - WACC) / WACC
            rim_value = bps + (bps * (roe - WACC) / WACC) if roe > WACC else bps

            # 4. 통계적 보수형 DCF (과거 현금흐름/매출 기반 하위 30% 성장률 적용)
            # yfinance는 통상 최근 4년치 데이터 제공. 이를 바탕으로 보수적 추세 산출
            dcf_value = 0
            if 'Free Cash Flow' in cashflow.index:
                fcf_history = cashflow.loc['Free Cash Flow'].dropna().values[::-1] # 과거->현재 순
                if len(fcf_history) >= 3 and all(f > 0 for f in fcf_history):
                    # 성장률 추이 계산
                    growth_rates = np.diff(fcf_history) / fcf_history[:-1]
                    mu = np.mean(growth_rates)
                    sigma = np.std(growth_rates)
                    
                    # 하위 30% 보수적 성장률 (Z-score: -0.52)
                    conservative_g = mu - (0.52 * sigma)
                    
                    # 기저효과 방지: 최대 성장률 15%, 최소 2% (인플레이션) 로 캡 설정
                    g = max(0.02, min(conservative_g, 0.15))
                    
                    # 5년 DCF 및 터미널 밸류 계산 (영구성장률 2.5% 고정)
                    fcf_0 = fcf_history[-1] / info.get('sharesOutstanding', 1) # 주당 FCF
                    present_value = 0
                    for year in range(1, 6):
                        fcf_t = fcf_0 * ((1 + g) ** year)
                        present_value += fcf_t / ((1 + WACC) ** year)
                    
                    # 터미널 밸류
                    tv = (fcf_0 * ((1 + g) ** 5) * (1 + 0.025)) / (WACC - 0.025)
                    present_value += tv / ((1 + WACC) ** 5)
                    dcf_value = present_value
                else:
                    dcf_value = epv_value # FCF 데이터 불량 시 EPV로 대체

            # ---------------------------------------------------------
            # 📊 결과 종합 및 판별
            # ---------------------------------------------------------
            # 가장 가혹한(가장 낮은) 적정 주가를 방어선으로 설정
            models = {'Graham': graham_value, 'EPV': epv_value, 'RIM': rim_value, 'Stat-DCF': dcf_value}
            strict_fair_value = min(models.values())
            
            st.subheader(f"📊 {info.get('shortName', ticker_input)} ({ticker_input}) 가치 평가 결과")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("현재 주가", f"${current_price:,.2f}")
            col2.metric("가장 보수적인 적정 주가", f"${strict_fair_value:,.2f}")
            
            margin_of_safety = ((strict_fair_value - current_price) / strict_fair_value) * 100
            col3.metric("안전 마진 (Margin of Safety)", f"{margin_of_safety:,.1f}%")
            
            if current_price < strict_fair_value:
                col4.success("🟢 STRONG BUY (저평가)")
            elif current_price < strict_fair_value * 1.1: # 10% 할증까지는 적정
                col4.warning("🟡 HOLD (적정 가치)")
            else:
                col4.error("🔴 SELL (고평가)")

            st.markdown("---")
            st.markdown("### ⚙️ 4대 엔진 개별 산출가")
            
            st.info(f"**1. 그레이엄 내재가치 (Graham):** ${graham_value:,.2f} \n\n (성장 배제. EPS와 BPS만을 이용한 전통적 가치)")
            st.info(f"**2. 잔여이익모델 (RIM):** ${rim_value:,.2f} \n\n (요구수익률 초과 이익 가치화. 버핏의 선호 방식)")
            st.info(f"**3. 수익력 가치 (EPV):** ${epv_value:,.2f} \n\n (미래 성장률 0%로 가정한 가장 가혹한 모델)")
            st.info(f"**4. 통계적 보수형 DCF:** ${dcf_value:,.2f} \n\n (과거 변동성 기반 '하위 30%' 보수적 성장률 적용)")
            
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다. 티커가 정확한지 확인해주세요. (Error: {e})")

st.markdown("---")
st.caption("주의: 본 대시보드는 재무제표 기반의 기계적/보수적 가치 평가를 수행하며, 미래의 시장 상황(매크로, 테마)을 반영하지 않습니다.")
