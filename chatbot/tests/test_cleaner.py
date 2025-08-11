from chatbot.cleaner import clean_bot_message

def test_clean_bot_message():
    raw = " سلام ,,\nدنیا!!  "
    cleaned = clean_bot_message(raw)
    assert "سلام" in cleaned and "دنیا" in cleaned
