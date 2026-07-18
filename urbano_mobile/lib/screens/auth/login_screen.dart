import 'package:flutter/material.dart';
import '../../utils/translations.dart';

import '../../services/auth_service.dart';
import '../home/home_screen.dart';

class LoginScreen extends StatefulWidget {
  @override
  _LoginScreenState createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> with SingleTickerProviderStateMixin {
  final AuthService _authService = AuthService();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _otpController = TextEditingController();

  late AnimationController _animationController;
  late Animation<double> _animation;

  bool _isOtpSent = false;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _animationController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 3),
    );
    _animation = Tween<double>(begin: 0.9, end: 1.1).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    ));
    _animationController.repeat(reverse: true);
  }

  @override
  void dispose() {
    _animationController.dispose();
    _emailController.dispose();
    _otpController.dispose();
    super.dispose();
  }

  void _sendOtp() async {
    final email = _emailController.text.trim();
    if (email.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Please enter an email')));
      return;
    }
    if (!RegExp(r"^[a-zA-Z0-9.a-zA-Z0-9.!#$%&'*+-/=?^_`{|}~]+@[a-zA-Z0-9]+\.[a-zA-Z]+").hasMatch(email)) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Please enter a valid email address')));
      return;
    }

    setState(() => _isLoading = true);

    final response = await _authService.sendOtp(email);

    setState(() => _isLoading = false);

    if (response['success'] == true) {
      setState(() => _isOtpSent = true);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('OTP Sent! Check your email.')));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(response['error'] ?? 'Unknown error')));
    }
  }

  void _verifyOtp() async {
    final email = _emailController.text.trim();
    final otp = _otpController.text.trim();

    if (otp.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Please enter the OTP')));
      return;
    }

    setState(() => _isLoading = true);

    final response = await _authService.verifyOtp(email, otp);

    setState(() => _isLoading = false);

    if (response['success'] == true) {
      // Login successful, navigate to Home Screen and prevent going back to Login
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (context) => HomeScreen()),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(response['error'] ?? 'Invalid OTP')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Urbano Login')),
      backgroundColor: Color(0xFFF0F4F8), // Light color background
      body: Stack(
        children: [
          // Animated Background Logo
          Center(
            child: ScaleTransition(
              scale: _animation,
              child: Opacity(
                opacity: 0.4,
                child: Image.asset(
                  'assets/logo.png',
                  width: 300,
                  height: 300,
                ),
              ),
            ),
          ),
          // Foreground Content
          SingleChildScrollView(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                SizedBox(height: 40),
                Text(
                  'Welcome to Urbano',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Color(0xFF1E3535)),
                  textAlign: TextAlign.center,
                ),
                SizedBox(height: 40),
                Card(
                  elevation: 2,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  color: Colors.white.withOpacity(0.95), // Translucent card to see background
                  child: Padding(
                    padding: const EdgeInsets.all(20.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        TextField(
                          controller: _emailController,
                          decoration: InputDecoration(
                            labelText: AppTranslations.get('email_address'),
                            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                            prefixIcon: Icon(Icons.email),
                          ),
                          keyboardType: TextInputType.emailAddress,
                          enabled: !_isOtpSent, // Lock email once OTP is sent
                        ),
                        SizedBox(height: 20),
                        
                        // Only show OTP field if OTP has been sent
                        if (_isOtpSent)
                          TextField(
                            controller: _otpController,
                            decoration: InputDecoration(
                              labelText: AppTranslations.get('6_digit_otp'),
                              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                              prefixIcon: Icon(Icons.lock),
                            ),
                            keyboardType: TextInputType.number,
                          ),
                          
                        SizedBox(height: 30),
                        
                        // Show loading spinner or the appropriate button
                        if (_isLoading)
                          Center(child: CircularProgressIndicator())
                        else
                          ElevatedButton(
                            onPressed: _isOtpSent ? _verifyOtp : _sendOtp,
                            style: ElevatedButton.styleFrom(
                              padding: EdgeInsets.symmetric(vertical: 16),
                            ),
                            child: Text(
                              _isOtpSent ? 'Verify & Login' : 'Send OTP',
                              style: TextStyle(fontSize: 18),
                            ),
                          ),
                        if (_isOtpSent && !_isLoading) ...[
                          SizedBox(height: 10),
                          TextButton(
                            onPressed: _sendOtp,
                            child: Text(AppTranslations.get('resend_otp'), style: TextStyle(color: Color(0xFF0D9488))),
                          ),
                        ],
                        ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
