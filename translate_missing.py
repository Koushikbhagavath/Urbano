import os, re
from deep_translator import GoogleTranslator

languages = {'kn': 'kannada', 'ta': 'tamil', 'ml': 'malayalam', 'hi': 'hindi', 'te': 'telugu'}
translators = {code: GoogleTranslator(source='en', target=code) for code in languages.keys()}

missing_strings = [
    "Tap to add photos and videos",
    "Edit Profile",
    "Camera (Photo)",
    "Video Library",
    "Verify & Save",
    "Nearest Landmark",
    "Location permissions are denied.",
    "6-Digit OTP",
    "URBANO",
    "Contact & Helpline",
    "1800-123-4567 (Toll Free)",
    "Email Address",
    "Please complete your profile in the sidebar menu to submit complaints.",
    "Mobile Number",
    "Profile updated successfully",
    "Gallery (Photo)",
    "Video Camera"
]

trans_file = r'd:\Projects\Urbano\urbano_mobile\lib\utils\translations.dart'
with open(trans_file, 'r', encoding='utf-8') as f:
    trans_content = f.read()

def make_key(text):
    k = re.sub(r'[^a-zA-Z0-9]', '_', text.lower())
    return re.sub(r'_+', '_', k).strip('_')

print("Translating...")
lang_maps = { 'en': {}, 'kn': {}, 'ta': {}, 'ml': {}, 'hi': {}, 'te': {} }
new_keys_map = {}

for text in missing_strings:
    key = make_key(text)
    new_keys_map[text] = key
    lang_maps['en'][key] = text
    for code in languages.keys():
        try:
            res = translators[code].translate(text)
            lang_maps[code][key] = res
            print(f"Translated {code}: {res}")
        except Exception as e:
            lang_maps[code][key] = text
            print(f"Failed {code} for {text}")

for code in ['en', 'kn', 'ta', 'ml', 'hi', 'te']:
    add_str = ""
    for k, v in lang_maps[code].items():
        v_esc = v.replace("'", "\\'")
        add_str += f"      '{k}': '{v_esc}',\n"
    target = f"'{code}': {{\n"
    idx = trans_content.find(target)
    if idx != -1:
        insert_pos = idx + len(target)
        trans_content = trans_content[:insert_pos] + add_str + trans_content[insert_pos:]

with open(trans_file, 'w', encoding='utf-8') as f:
    f.write(trans_content)

print("Translations written. Now replacing in dart files.")

import glob
dart_files = glob.glob(r'd:\Projects\Urbano\urbano_mobile\lib\screens\**\*.dart', recursive=True)
dart_files.append(r'd:\Projects\Urbano\urbano_mobile\lib\widgets\animated_background.dart')

for file in dart_files:
    if 'language_selection_screen.dart' in file: continue
    with open(file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    for text, key in new_keys_map.items():
        escaped_text = re.escape(text)
        content = re.sub(r"Text\(\s*'" + escaped_text + r"'\s*(,|\))", r"Text(AppTranslations.get('" + key + r"')\1", content)
        content = re.sub(r'Text\(\s*"' + escaped_text + r'"\s*(,|\))', r"Text(AppTranslations.get('" + key + r"')\1", content)
        content = re.sub(r"labelText:\s*'" + escaped_text + r"'", r"labelText: AppTranslations.get('" + key + r"')", content)
        content = re.sub(r'labelText:\s*"' + escaped_text + r'"', r"labelText: AppTranslations.get('" + key + r"')", content)
        content = re.sub(r"hintText:\s*'" + escaped_text + r"'", r"hintText: AppTranslations.get('" + key + r"')", content)
        content = re.sub(r'hintText:\s*"' + escaped_text + r'"', r"hintText: AppTranslations.get('" + key + r"')", content)

    if content != original_content:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)

print("Done replacing.")
