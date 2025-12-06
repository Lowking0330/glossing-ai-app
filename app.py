import streamlit as st
import google.generativeai as genai
import importlib.metadata

st.set_page_config(page_title="Gemini 模型診斷工具", page_icon="🕵️")

st.title("🕵️ Gemini 模型與環境診斷工具")
st.markdown("這支程式會幫您檢查「套件版本」以及「實際可用的模型清單」。")
st.markdown("---")

# ==========================================
# 1. 檢查 Python 套件版本 (關鍵步驟)
# ==========================================
st.subheader("1. 環境檢查")
try:
    # 嘗試抓取安裝版本
    lib_version = importlib.metadata.version("google-generativeai")
    st.write(f"您目前安裝的 `google-generativeai` 版本為： **{lib_version}**")
    
    # 判斷版本是否過舊
    # 0.5.0 以上才支援 1.5 模型
    # 0.8.0 以上才支援 1.5 Flash 穩定版
    if lib_version < "0.5.0":
        st.error("❌ 版本極舊！這就是導致 404 錯誤的主因。您必須更新到 0.8.3 以上。")
        st.info("解決方法：請更新 requirements.txt，加上 `google-generativeai>=0.8.3`")
    elif lib_version < "0.8.3":
        st.warning("⚠️ 版本稍舊，可能不支援最新的 'gemini-1.5-flash' 名稱。")
    else:
        st.success("✅ 套件版本足夠新，應該能支援所有模型。")

except Exception as e:
    st.warning(f"無法偵測套件版本 (可能未安裝或環境異常): {e}")

st.markdown("---")

# ==========================================
# 2. 查詢可用模型
# ==========================================
st.subheader("2. 查詢 Google 伺服器上的可用模型")

# 優先讀取 Secrets，沒有則手動輸入
default_key = st.secrets.get("GEMINI_API_KEY", "")
api_key = st.text_input("請輸入 API Key", value=default_key, type="password")

if st.button("開始掃描可用模型", type="primary"):
    if not api_key:
        st.error("請輸入 API Key 才能查詢。")
    else:
        try:
            genai.configure(api_key=api_key)
            
            st.write("正在連線 Google 查詢中...")
            available_models = []
            
            # 列出所有模型
            for m in genai.list_models():
                # 我們只關心能「產生文字 (generateContent)」的模型
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            
            if available_models:
                st.success(f"🎉 查詢成功！您的 API Key 目前可以使用以下 {len(available_models)} 個模型：")
                
                # 顯示程式碼區塊，方便複製
                st.markdown("### 👇 請複製以下任一名稱填入您的程式碼中：")
                for name in available_models:
                    st.code(f"model = genai.GenerativeModel('{name.replace('models/', '')}')")
                    # 附註說明
                    if "flash" in name:
                        st.caption("👆 (推薦) 速度快、免費額度高")
                    elif "pro" in name:
                        st.caption("👆 (推薦) 性能均衡")
            else:
                st.error("連線成功，但沒有找到任何支援 generateContent 的模型。這很不尋常。")

        except Exception as e:
            st.error(f"❌ 查詢失敗，錯誤訊息：{e}")
            if "404" in str(e):
                st.markdown("👉 **結論**：這證實了您的套件版本太舊，舊到連 `list_models` 的 API 路徑都跟現在不一樣了。請務必更新 `requirements.txt`。")
