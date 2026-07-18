import re

with open(r'd:\Projects\Urbano\urbano_mobile\lib\utils\translations.dart', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the incorrectly escaped quotes
text = text.replace("\\'", "'")

# We want to restore actual newlines for formatting, EXCEPT inside values.
# The structure right now is:
# 'key': 'value',\n
# But wait, the file literally has "\n" (backslash n) where structural newlines should be.
# Let's split the file by the literal string "\n"
lines = text.split("\\n")

fixed_lines = []
for line in lines:
    # If the line contains a value with an actual newline that we WANT to be \n,
    # wait, my previous broken python script did:
    # content = re.sub(r'\'([^\']+?)\n([^\']+?)\'', r'\'\1\\n\2\'', content)
    # The broken python script literally replaced all \n in the file with \\n because the regex `[^\']` matched EVERYTHING that wasn't a single quote, crossing structural boundaries!
    # Ah! The regex matched across the whole file.

    fixed_lines.append(line)

# Let's just completely reconstruct the dictionary from the current text.
# We can find all keys and values for each language.
# The text looks like: 'en': {      'complaint_details': 'Complaint Details',      'no_media_attached': 'No media attached', ... }

# Let's extract everything inside 'en': { ... }
langs = ['en', 'kn', 'ta', 'ml', 'hi', 'te']

dart_code = "class AppTranslations {\n  static const Map<String, Map<String, String>> translations = {\n"

for lang in langs:
    # find the block for lang
    # the block starts with `'lang': {` and ends with `},`
    pattern = rf"'{lang}': {{(.*?)\}},"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        continue
    
    block = match.group(1)
    
    # Now extract all 'key': 'value' pairs
    # Values might contain \n (literal or otherwise)
    pairs = re.findall(r"'([^']+)': '([^']+)'", block)
    
    dart_code += f"    '{lang}': {{\n"
    for k, v in pairs:
        # If the value has an actual newline in it, replace it with \\n
        v = v.replace('\n', '\\n')
        # If the value has literal \n, keep it
        dart_code += f"      '{k}': '{v}',\n"
    dart_code += "    },\n"

dart_code += "  };\n\n  static String currentLanguage = 'en';\n\n  static String get(String key) {\n    return translations[currentLanguage]?[key] ?? translations['en']?[key] ?? key;\n  }\n}\n"

with open(r'd:\Projects\Urbano\urbano_mobile\lib\utils\translations.dart', 'w', encoding='utf-8') as f:
    f.write(dart_code)

print("Translations reconstructed.")
