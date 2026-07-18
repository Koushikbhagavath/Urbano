import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../utils/translations.dart';

import '../../services/api_service.dart';
import '../../services/auth_service.dart';
import '../auth/login_screen.dart';

class ProfileDrawer extends StatefulWidget {
  final Map<String, dynamic>? initialProfile;
  final VoidCallback onProfileUpdated;

  ProfileDrawer({this.initialProfile, required this.onProfileUpdated});

  @override
  _ProfileDrawerState createState() => _ProfileDrawerState();
}

class _ProfileDrawerState extends State<ProfileDrawer> {
  final _formKey = GlobalKey<FormState>();
  final ApiService _apiService = ApiService();
  final AuthService _authService = AuthService();

  late TextEditingController _nameController;
  late TextEditingController _emailController;
  late TextEditingController _mobileController;
  late TextEditingController _ageController;
  String? _gender;
  late TextEditingController _addressController;

  bool _isLoading = false;
  bool _isEditing = false;
  String _originalEmail = '';

  @override
  void initState() {
    super.initState();
    
    // Clean dummy values
    String name = widget.initialProfile?['name'] ?? '';
    if (name.contains('New Mobile User') || name.contains('new user registration')) {
      name = '';
    }
    
    String mobile = widget.initialProfile?['mobile_number'] ?? '';
    if (mobile.startsWith('OTP-')) {
      mobile = '';
    }

    _nameController = TextEditingController(text: name);
    _originalEmail = widget.initialProfile?['email'] ?? '';
    _emailController = TextEditingController(text: _originalEmail);
    _mobileController = TextEditingController(text: mobile);
    _ageController = TextEditingController(text: widget.initialProfile?['age']?.toString() ?? '');
    _gender = widget.initialProfile?['gender'];
    _addressController = TextEditingController(text: widget.initialProfile?['address'] ?? '');
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _mobileController.dispose();
    _ageController.dispose();
    _addressController.dispose();
    super.dispose();
  }

  void _saveProfile() async {
    if (_formKey.currentState!.validate()) {
      // If email changed, we must do OTP verification first
      if (_emailController.text != _originalEmail) {
        _requestEmailChangeOTP();
        return;
      }
      _performSave();
    }
  }

  void _performSave() async {
    setState(() => _isLoading = true);
    
    Map<String, dynamic> data = {
      'name': _nameController.text,
      'mobile_number': _mobileController.text,
      'age': int.tryParse(_ageController.text) ?? 0,
      'gender': _gender,
      'address': _addressController.text,
    };

    final response = await _apiService.updateProfile(data);
    
    setState(() => _isLoading = false);

    if (response['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('profile_updated_successfully'))));
      widget.onProfileUpdated();
      setState(() {
        _isEditing = false;
      });
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(response['error'] ?? 'Update failed')));
    }
  }

  void _requestEmailChangeOTP() async {
    setState(() => _isLoading = true);
    final response = await _apiService.requestEmailChange(_emailController.text);
    setState(() => _isLoading = false);

    if (response['success'] == true) {
      _showOTPDialog();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(response['error'] ?? 'Failed to send OTP')));
    }
  }

  void _showOTPDialog() {
    TextEditingController otpController = TextEditingController();
    bool isVerifying = false;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setStateDialog) {
            return AlertDialog(
              title: Text('Verify New Email'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('An OTP has been sent to ${_emailController.text}.'),
                  SizedBox(height: 10),
                  TextField(
                    controller: otpController,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(
                      labelText: 'Enter OTP',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () {
                    Navigator.pop(context);
                    // Revert email if they cancel
                    setState(() {
                      _emailController.text = _originalEmail;
                    });
                  },
                  child: Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: isVerifying ? null : () async {
                    if (otpController.text.isEmpty) return;
                    setStateDialog(() => isVerifying = true);
                    final response = await _apiService.verifyEmailChange(_emailController.text, otpController.text);
                    setStateDialog(() => isVerifying = false);

                    if (response['success'] == true) {
                      Navigator.pop(context); // close dialog
                      _originalEmail = _emailController.text; // Update original
                      _performSave(); // Continue saving the rest of the profile
                    } else {
                      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(response['error'] ?? 'Invalid OTP')));
                    }
                  },
                  child: isVerifying ? SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : Text(AppTranslations.get('verify_save')),
                ),
              ],
            );
          }
        );
      }
    );
  }

  void _logout() async {
    await _authService.logout();
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (context) => LoginScreen()),
      (Route<dynamic> route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    double completion = 0;
    int filled = 0;
    if (_nameController.text.isNotEmpty) filled++;
    if (_emailController.text.isNotEmpty) filled++;
    if (_mobileController.text.isNotEmpty && !_mobileController.text.startsWith('OTP-')) filled++;
    if (_ageController.text.isNotEmpty) filled++;
    if (_addressController.text.isNotEmpty) filled++;
    completion = filled / 5.0;

    return Drawer(
      child: SafeArea(
        child: Column(
          children: [
            Container(
              padding: EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              width: double.infinity,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [Colors.teal.shade800, Colors.teal.shade500],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
              ),
              child: Stack(
                clipBehavior: Clip.none,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      CircleAvatar(
                        radius: 36,
                        backgroundColor: Colors.white,
                        child: Icon(Icons.person_outline, size: 40, color: Colors.teal.shade700),
                      ),
                      SizedBox(height: 16),
                      Text(
                        _nameController.text.isNotEmpty ? _nameController.text : AppTranslations.get('new_user'),
                        style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold, letterSpacing: 0.5),
                        maxLines: 1, overflow: TextOverflow.ellipsis,
                      ),
                      SizedBox(height: 4),
                      Text(_originalEmail, style: TextStyle(color: Colors.teal.shade100, fontSize: 14)),
                      SizedBox(height: 20),
                      Row(
                        children: [
                          Expanded(
                            child: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: LinearProgressIndicator(
                                value: completion,
                                minHeight: 6,
                                backgroundColor: Colors.teal.shade900.withOpacity(0.5),
                                valueColor: AlwaysStoppedAnimation<Color>(Colors.greenAccent),
                              ),
                            ),
                          ),
                          SizedBox(width: 12),
                          Text('${(completion * 100).toInt()}%', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12)),
                        ],
                      ),
                      SizedBox(height: 4),
                      Text(AppTranslations.get('profile_completion'), style: TextStyle(color: Colors.teal.shade200, fontSize: 10)),
                      SizedBox(height: 16),
                      ElevatedButton.icon(
                        onPressed: () {
                          setState(() {
                            _isEditing = !_isEditing;
                            if (!_isEditing) {
                              _emailController.text = _originalEmail;
                            }
                          });
                        },
                        icon: Icon(_isEditing ? Icons.close : Icons.edit, size: 16),
                        label: Text(_isEditing ? AppTranslations.get('cancel_edit') : AppTranslations.get('edit_profile'), style: TextStyle(fontWeight: FontWeight.bold)),
                        style: ElevatedButton.styleFrom(
                          foregroundColor: Colors.teal.shade800,
                          backgroundColor: Colors.white,
                          padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                          elevation: 2,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: EdgeInsets.only(
                  left: 16,
                  right: 16,
                  top: 16,
                  bottom: MediaQuery.of(context).viewInsets.bottom + 16,
                ),
                child: Form(
                  key: _formKey,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (!_isEditing)
                        Text(AppTranslations.get('profile_is_in_read_only_mode_click_the_pen_icon_above_to_edit_'), style: TextStyle(color: Colors.grey[600], fontSize: 12)),
                      if (_isEditing)
                        Text(AppTranslations.get('edit_your_profile_changing_email_requires_otp_'), style: TextStyle(color: Colors.blue[600], fontSize: 12)),
                      SizedBox(height: 15),
                      TextFormField(
                        controller: _emailController,
                        enabled: _isEditing,
                        decoration: InputDecoration(labelText: AppTranslations.get('email_address'), border: OutlineInputBorder(), filled: true, fillColor: Colors.grey[50]),
                        validator: (value) {
                          if (value == null || value.isEmpty) return AppTranslations.get('required');
                          if (!RegExp(r"^[a-zA-Z0-9.a-zA-Z0-9.!#$%&'*+-/=?^_`{|}~]+@[a-zA-Z0-9]+\.[a-zA-Z]+").hasMatch(value)) return 'Invalid email';
                          return null;
                        },
                      ),
                      SizedBox(height: 15),
                      TextFormField(
                        controller: _nameController,
                        enabled: _isEditing,
                        decoration: InputDecoration(labelText: AppTranslations.get('full_name'), border: OutlineInputBorder(), filled: true, fillColor: Colors.grey[50]),
                        validator: (value) {
                          if (value == null || value.isEmpty) return AppTranslations.get('required');
                          if (value.trim().length < 3) return 'Name too short';
                          return null;
                        },
                      ),
                      SizedBox(height: 15),
                      TextFormField(
                        controller: _mobileController,
                        enabled: _isEditing,
                        maxLength: 10,
                        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                        decoration: InputDecoration(labelText: AppTranslations.get('mobile_number'), border: OutlineInputBorder(), filled: true, fillColor: Colors.grey[50], counterText: ''),
                        keyboardType: TextInputType.phone,
                        validator: (value) {
                          if (value == null || value.isEmpty) return AppTranslations.get('required');
                          if (value.length != 10) return 'Must be 10 digits';
                          return null;
                        },
                      ),
                      SizedBox(height: 15),
                      Row(
                        children: [
                          Expanded(
                            child: TextFormField(
                              controller: _ageController,
                              enabled: _isEditing,
                              maxLength: 3,
                              inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                              decoration: InputDecoration(labelText: AppTranslations.get('age'), border: OutlineInputBorder(), filled: true, fillColor: Colors.grey[50], counterText: ''),
                              keyboardType: TextInputType.number,
                              validator: (value) {
                                if (value == null || value.isEmpty) return AppTranslations.get('required');
                                int? age = int.tryParse(value);
                                if (age == null || age < 1 || age > 120) return 'Invalid age';
                                return null;
                              },
                            ),
                          ),
                          SizedBox(width: 15),
                          Expanded(
                            child: DropdownButtonFormField<String>(
                              decoration: InputDecoration(labelText: AppTranslations.get('gender'), border: OutlineInputBorder(), filled: true, fillColor: Colors.grey[50]),
                              value: _gender,
                              items: ['Male', 'Female', 'Other'].map((String value) {
                                return DropdownMenuItem<String>(value: value, child: Text(AppTranslations.get(value.toLowerCase())));
                              }).toList(),
                              onChanged: _isEditing ? (newValue) => setState(() => _gender = newValue) : null,
                              validator: (value) => value == null ? AppTranslations.get('required') : null,
                            ),
                          ),
                        ],
                      ),
                      SizedBox(height: 15),
                      TextFormField(
                        controller: _addressController,
                        enabled: _isEditing,
                        decoration: InputDecoration(labelText: AppTranslations.get('full_address'), border: OutlineInputBorder(), filled: true, fillColor: Colors.grey[50]),
                        maxLines: 3,
                        validator: (value) => value!.isEmpty ? AppTranslations.get('required') : null,
                      ),
                      SizedBox(height: 20),
                      if (_isEditing)
                        ElevatedButton(
                          onPressed: _isLoading ? null : _saveProfile,
                          child: _isLoading ? SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)) : Text(AppTranslations.get('save_profile'), style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1.1)),
                          style: ElevatedButton.styleFrom(
                            padding: EdgeInsets.symmetric(vertical: 18),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            backgroundColor: Colors.teal,
                            foregroundColor: Colors.white,
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            Divider(height: 1),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(AppTranslations.get('contact_helpline'), style: TextStyle(fontWeight: FontWeight.bold, color: Colors.teal[800], fontSize: 13)),
                  SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.phone, size: 14, color: Colors.grey[600]),
                      SizedBox(width: 8),
                      Text(AppTranslations.get('1800_123_4567_toll_free'), style: TextStyle(color: Colors.grey[600], fontSize: 13)),
                    ],
                  ),
                  SizedBox(height: 2),
                  Row(
                    children: [
                      Icon(Icons.email, size: 14, color: Colors.grey[600]),
                      SizedBox(width: 8),
                      Text('support@urbano.com', style: TextStyle(color: Colors.grey[600], fontSize: 13)),
                    ],
                  ),
                ],
              ),
            ),
            Divider(height: 1),
            ListTile(
              leading: Icon(Icons.logout, color: Colors.red),
              title: Text(AppTranslations.get('logout'), style: TextStyle(color: Colors.red)),
              onTap: _logout,
            ),
          ],
        ),
      ),
    );
  }
}
