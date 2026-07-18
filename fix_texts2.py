import os, re
import urllib.request
import json

missing = {
    "Complaint Details": "ದೂರು ವಿವರಗಳು",
    "No media attached": "ಯಾವುದೇ ಮಾಧ್ಯಮ ಲಗತ್ತಿಸಿಲ್ಲ",
    "COMPLAINT": "ದೂರು",
    "Date N/A": "ದಿನಾಂಕ N/A",
    "Timeline": "ಟೈಮ್‌ಲೈನ್",
    "No status history available.": "ಯಾವುದೇ ಸ್ಥಿತಿ ಇತಿಹಾಸ ಲಭ್ಯವಿಲ್ಲ.",
    "By": "ವತಿಯಿಂದ:",
    "on": "ರಂದು:",
    "Loading Video...": "ವೀಡಿಯೊ ಲೋಡ್ ಆಗುತ್ತಿದೆ..."
}

lang_maps = { 'en': {}, 'kn': {}, 'ta': {}, 'ml': {}, 'hi': {}, 'te': {} }

def make_key(text):
    k = re.sub(r'[^a-zA-Z0-9]', '_', text.lower())
    return re.sub(r'_+', '_', k).strip('_')

for en_text, kn_text in missing.items():
    key = make_key(en_text)
    lang_maps['en'][key] = en_text
    for code in ['kn', 'ta', 'ml', 'hi', 'te']:
        lang_maps[code][key] = kn_text

trans_file = r'd:\Projects\Urbano\urbano_mobile\lib\utils\translations.dart'
with open(trans_file, 'r', encoding='utf-8') as f:
    trans_content = f.read()

for code in ['en', 'kn', 'ta', 'ml', 'hi', 'te']:
    add_str = ""
    for k, v in lang_maps[code].items():
        v_esc = v.replace("'", "\\'")
        if f"'{k}':" not in trans_content:
            add_str += f"      '{k}': '{v_esc}',\n"
    
    target = f"'{code}': {{\n"
    idx = trans_content.find(target)
    if idx != -1:
        insert_pos = idx + len(target)
        trans_content = trans_content[:insert_pos] + add_str + trans_content[insert_pos:]

with open(trans_file, 'w', encoding='utf-8') as f:
    f.write(trans_content)

print("Translations written 2.")
