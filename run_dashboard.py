import streamlit as st

from app.dashboard import main  # type: ignore

st.set_page_config(page_title='Trading Dashboard', page_icon='💰', layout="wide")

main()
