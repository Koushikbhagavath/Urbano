import 'package:translator/translator.dart';
import 'translations.dart';

class TranslationHelper {
  static final GoogleTranslator _translator = GoogleTranslator();
  static final Map<String, String> _cache = {};

  static Future<String> translateText(String text) async {
    if (text.isEmpty) return text;
    String targetLang = AppTranslations.currentLanguage;
    
    // Create a cache key
    String key = '${text.hashCode}_$targetLang';
    if (_cache.containsKey(key)) {
      return _cache[key]!;
    }
    
    try {
      var translation = await _translator.translate(text, to: targetLang);
      _cache[key] = translation.text;
      return translation.text;
    } catch (e) {
      print('Translation Error: $e');
      return text;
    }
  }
}
