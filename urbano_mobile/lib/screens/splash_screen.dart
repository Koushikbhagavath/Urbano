import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/auth_service.dart';
import 'auth/login_screen.dart';
import 'home/home_screen.dart';
import '../utils/translations.dart';
import 'language/language_selection_screen.dart';

class SplashScreen extends StatefulWidget {
  @override
  _SplashScreenState createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: Duration(seconds: 2),
    );
    _animation = Tween<double>(begin: 0.8, end: 1.1).animate(CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOut,
    ));

    _controller.repeat(reverse: true);
    
    Future.delayed(Duration(seconds: 3), () {
      _navigateToNext();
    });
  }

  void _navigateToNext() async {
    bool isLoggedIn = await AuthService().isLoggedIn();
    
    // Check if language is selected
    SharedPreferences prefs = await SharedPreferences.getInstance();
    bool hasSelectedLanguage = prefs.getBool('has_selected_language') ?? false;
    
    // Load saved language
    String savedLang = prefs.getString('app_language') ?? 'en';
    AppTranslations.currentLanguage = savedLang;

    // Slight pause before transition
    await Future.delayed(Duration(milliseconds: 500));
    
    if (!mounted) return;

    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        transitionDuration: Duration(milliseconds: 800),
        pageBuilder: (context, animation, secondaryAnimation) {
          if (!hasSelectedLanguage) return LanguageSelectionScreen();
          return isLoggedIn ? HomeScreen() : LoginScreen();
        },
        transitionsBuilder: (context, animation, secondaryAnimation, child) {
          return FadeTransition(
            opacity: animation,
            child: child,
          );
        },
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Color(0xFFF0F4F8), // Light color background
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ScaleTransition(
              scale: _animation,
              child: Image.asset(
                'assets/logo.png',
                width: 150,
                height: 150,
              ),
            ),
            SizedBox(height: 30),
            Text(AppTranslations.get('urbano'),
              style: TextStyle(
                color: Color(0xFF1E3535),
                fontSize: 34,
                fontWeight: FontWeight.bold,
                letterSpacing: 3.0,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
