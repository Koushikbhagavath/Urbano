import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../utils/constants.dart';

class AuthService {
  // 1. Request OTP from the Python backend
  Future<Map<String, dynamic>> sendOtp(String email) async {
    try {
      final response = await http.post(
        Uri.parse('${AppConstants.baseUrl}/send_otp'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: jsonEncode({'email': email}),
      ).timeout(const Duration(seconds: 120));

      return jsonDecode(response.body);
    } catch (e) {
      return {'success': false, 'error': 'Failed to connect to server: $e'};
    }
  }

  // 2. Verify OTP and save the user session
  Future<Map<String, dynamic>> verifyOtp(String email, String otp) async {
    try {
      final response = await http.post(
        Uri.parse('${AppConstants.baseUrl}/verify_otp'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: jsonEncode({'email': email, 'otp': otp}),
      ).timeout(const Duration(seconds: 120));

      final data = jsonDecode(response.body);

      // If successful, save the user_id locally to bypass login screen later
      if (response.statusCode == 200 && data['success'] == true) {
        final prefs = await SharedPreferences.getInstance();
        await prefs.setInt('user_id', data['user_id']);
      }

      return data;
    } catch (e) {
      return {'success': false, 'error': 'Failed to connect to server: $e'};
    }
  }

  // 3. Log the user out by clearing the saved user_id
  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('user_id');
  }

  // 4. Check if the user is already logged in
  Future<bool> isLoggedIn() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.containsKey('user_id');
  }
}
