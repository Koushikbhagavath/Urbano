import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http_parser/http_parser.dart';
import '../utils/constants.dart';
import 'dart:io';
import 'package:dio/dio.dart';

class ApiService {
  // Get user profile
  Future<Map<String, dynamic>> getProfile() async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getInt('user_id');
    if (userId == null) return {'success': false, 'error': 'Not logged in'};

    try {
      final response = await http.get(
        Uri.parse('${AppConstants.baseUrl}/user/profile?user_id=$userId'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      ).timeout(const Duration(seconds: 30));
      return jsonDecode(response.body);
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  // Update user profile
  Future<Map<String, dynamic>> updateProfile(Map<String, dynamic> data) async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getInt('user_id');
    if (userId == null) return {'success': false, 'error': 'Not logged in'};

    data['user_id'] = userId;

    try {
      final response = await http.post(
        Uri.parse('${AppConstants.baseUrl}/user/update_profile'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: jsonEncode(data),
      ).timeout(const Duration(seconds: 30));
      return jsonDecode(response.body);
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  // Request Email Change
  Future<Map<String, dynamic>> requestEmailChange(String newEmail) async {
    try {
      final response = await http.post(
        Uri.parse('${AppConstants.baseUrl}/user/request_email_change'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: jsonEncode({'new_email': newEmail}),
      ).timeout(const Duration(seconds: 30));
      return jsonDecode(response.body);
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  // Verify Email Change
  Future<Map<String, dynamic>> verifyEmailChange(String newEmail, String otp) async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getInt('user_id');
    if (userId == null) return {'success': false, 'error': 'Not logged in'};

    try {
      final response = await http.post(
        Uri.parse('${AppConstants.baseUrl}/user/verify_email_change'),
        headers: {
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': 'true'
        },
        body: jsonEncode({
          'user_id': userId,
          'new_email': newEmail,
          'otp': otp
        }),
      ).timeout(const Duration(seconds: 30));
      return jsonDecode(response.body);
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  // Get user complaints
  Future<Map<String, dynamic>> getComplaints() async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getInt('user_id');
    if (userId == null) return {'success': false, 'error': 'Not logged in'};

    try {
      final response = await http.get(
        Uri.parse('${AppConstants.baseUrl}/user/complaints?user_id=$userId'),
        headers: {'ngrok-skip-browser-warning': 'true'},
      ).timeout(const Duration(seconds: 30));
      return jsonDecode(response.body);
    } catch (e) {
      return {'success': false, 'error': 'Network error: $e'};
    }
  }

  // Submit new complaint with an optional image
  Future<Map<String, dynamic>> submitComplaint({
    required String title,
    required String details,
    required String landmark,
    required String address,
    required String city,
    required double latitude,
    required double longitude,
    List<File>? mediaFiles,
    void Function(int, int)? onSendProgress,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getInt('user_id');
    if (userId == null) return {'success': false, 'error': 'Not logged in'};

    try {
      final dio = Dio();
      dio.options.connectTimeout = const Duration(seconds: 15);
      dio.options.receiveTimeout = const Duration(seconds: 45);

      var formData = FormData.fromMap({
        'user_id': userId.toString(),
        'title': title,
        'details': details,
        'landmark': landmark,
        'address': address,
        'city': city,
        'latitude': latitude.toString(),
        'longitude': longitude.toString(),
      });

      if (mediaFiles != null && mediaFiles.isNotEmpty) {
        for (var file in mediaFiles) {
          final ext = file.path.split('.').last.toLowerCase();
          final isVideo = ext == 'mp4' || ext == 'mov' || ext == 'avi';
          
          formData.files.add(MapEntry(
            'files',
            await MultipartFile.fromFile(
              file.path,
              contentType: MediaType(isVideo ? 'video' : 'image', ext == 'jpg' ? 'jpeg' : ext),
            ),
          ));
        }
      }

      final response = await dio.post(
        '${AppConstants.baseUrl}/submit_complaint',
        data: formData,
        options: Options(headers: {'ngrok-skip-browser-warning': 'true'}),
        onSendProgress: onSendProgress,
      );

      if (response.data is String) {
        return jsonDecode(response.data);
      }
      return Map<String, dynamic>.from(response.data);
    } catch (e) {
      if (e is DioException) {
        return {'success': false, 'error': 'Server error: ${e.response?.data ?? e.message}'};
      }
      return {'success': false, 'error': 'Network error: $e'};
    }
  }
}
