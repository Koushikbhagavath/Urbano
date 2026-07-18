import 'package:flutter/material.dart';
import '../../utils/translations.dart';

import 'package:image_picker/image_picker.dart';
import 'dart:io';
import 'package:geolocator/geolocator.dart';
import 'package:video_compress/video_compress.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../../services/api_service.dart';
import '../../widgets/animated_background.dart';

class NewComplaintScreen extends StatefulWidget {
  @override
  _NewComplaintScreenState createState() => _NewComplaintScreenState();
}

class _NewComplaintScreenState extends State<NewComplaintScreen> {
  final _formKey = GlobalKey<FormState>();
  final ApiService _apiService = ApiService();
  final ImagePicker _picker = ImagePicker();

  String _title = '';
  String _details = '';
  String _landmark = '';
  String _address = '';
  String _city = 'Mysore'; // Default city
  List<File> _mediaFiles = [];
  bool _isLoading = false;
  bool _isUploading = false;
  double _uploadProgress = 0.0;
  
  double? _selectedLat;
  double? _selectedLng;
  final MapController _mapController = MapController();

  final List<String> _cities = [
    'Mysore',
    'Bangalore',
    'Mangalore',
    'Hubli',
  ];

  @override
  void initState() {
    super.initState();
    _fetchInitialLocation();
  }

  Future<void> _fetchInitialLocation() async {
    try {
      Position? position = await _determinePosition();
      if (position != null && mounted) {
        setState(() {
          _selectedLat = position.latitude;
          _selectedLng = position.longitude;
        });
        _mapController.move(LatLng(position.latitude, position.longitude), 15.0);
      }
    } catch (e) {
      // Ignore initial fetch errors
    }
  }

  Future<void> _pickMedia(ImageSource source, {bool isVideo = false}) async {
    if (isVideo) {
      if (_mediaFiles.any((f) => f.path.endsWith('.mp4') || f.path.endsWith('.mov') || f.path.endsWith('.avi'))) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('only_1_video_allowed'))));
        return;
      }
      final XFile? pickedFile = await _picker.pickVideo(source: source);
      if (pickedFile != null) {
        File file = File(pickedFile.path);
        
        setState(() => _isLoading = true);
        try {
          if (file.lengthSync() > 70 * 1024 * 1024) {
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('compressing_video_'))));
            final info = await VideoCompress.compressVideo(
              file.path,
              quality: VideoQuality.MediumQuality,
              deleteOrigin: false,
            );
            if (info != null && info.file != null) {
              file = info.file!;
            }
          }
        } finally {
          setState(() => _isLoading = false);
        }

        setState(() {
          _mediaFiles.add(file);
        });
      }
    } else {
      int photoCount = _mediaFiles.where((f) => !f.path.endsWith('.mp4') && !f.path.endsWith('.mov') && !f.path.endsWith('.avi')).length;
      if (source == ImageSource.gallery) {
        final List<XFile> pickedFiles = await _picker.pickMultiImage(imageQuality: 70);
        setState(() {
          for (var picked in pickedFiles) {
            if (photoCount < 3) {
              _mediaFiles.add(File(picked.path));
              photoCount++;
            } else {
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('max_3_photos_allowed'))));
              break;
            }
          }
        });
      } else {
        if (photoCount < 3) {
          final XFile? pickedFile = await _picker.pickImage(source: source, imageQuality: 70);
          if (pickedFile != null) {
            setState(() {
              _mediaFiles.add(File(pickedFile.path));
            });
          }
        } else {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Max 3 photos allowed')));
        }
      }
    }
  }

  Future<Position?> _determinePosition() async {
    bool serviceEnabled;
    LocationPermission permission;

    try {
      serviceEnabled = await Geolocator.isLocationServiceEnabled().timeout(const Duration(seconds: 5));
      if (!serviceEnabled) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('location_services_are_disabled_'))));
        return null;
      }

      permission = await Geolocator.checkPermission().timeout(const Duration(seconds: 5));
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission().timeout(const Duration(seconds: 10));
        if (permission == LocationPermission.denied) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('location_permissions_are_denied'))));
          return null;
        }
      }

      if (permission == LocationPermission.deniedForever) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('location_permissions_are_permanently_denied_we_cannot_request_permissions_'))));
        return null;
      }

      Position? pos = await Geolocator.getLastKnownPosition().timeout(const Duration(seconds: 5));
      if (pos != null) return pos;

      return await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(timeLimit: Duration(seconds: 15))
      ).timeout(const Duration(seconds: 15));
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('location_timeout_or_error_ensure_gps_is_fully_active_'))));
      return null;
    }
  }

  void _submit() async {
    if (_formKey.currentState!.validate()) {
      _formKey.currentState!.save();
      
      setState(() {
        _isLoading = true;
        _isUploading = false;
        _uploadProgress = 0.0;
      });
      
      if (_selectedLat == null || _selectedLng == null) {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _isUploading = false;
          });
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(AppTranslations.get('please_select_a_location_on_the_map_'))));
        }
        return; // Mandatory location requirement
      }
      
      try {
        if (mounted) setState(() => _isUploading = true);

        final response = await _apiService.submitComplaint(
          title: _title,
          details: _details,
          landmark: _landmark,
          address: _address,
          city: _city,
          latitude: _selectedLat!,
          longitude: _selectedLng!,
          mediaFiles: _mediaFiles,
          onSendProgress: (int sent, int total) {
            if (total != -1 && mounted) {
              setState(() {
                _uploadProgress = sent / total;
              });
            }
          },
        );

        if (!mounted) return;

        setState(() {
          _isLoading = false;
          _isUploading = false;
        });

        if (response['success'] == true) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(AppTranslations.get('complaint_submitted_successfully_'))),
          );
          Navigator.pop(context, true);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(response['error'] ?? 'Submission failed.')),
          );
        }
      } catch (e, stacktrace) {
        if (mounted) {
          setState(() {
            _isLoading = false;
            _isUploading = false;
          });
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(AppTranslations.get('an_unexpected_error_occurred_') + e.toString())),
          );
          print('Submit Error: $e\n$stacktrace');
        }
      }
    }
  }

  void _showImageSourceDialog() {
    showModalBottomSheet(
      context: context,
      builder: (context) => SafeArea(
        child: Wrap(
          children: <Widget>[
            ListTile(
              leading: Icon(Icons.photo_library),
              title: Text(AppTranslations.get('photo_library')),
              onTap: () {
                _pickMedia(ImageSource.gallery, isVideo: false);
                Navigator.of(context).pop();
              },
            ),
            ListTile(
              leading: Icon(Icons.photo_camera),
              title: Text(AppTranslations.get('camera_photo')),
              onTap: () {
                _pickMedia(ImageSource.camera, isVideo: false);
                Navigator.of(context).pop();
              },
            ),
            ListTile(
              leading: Icon(Icons.videocam),
              title: Text(AppTranslations.get('camera_video_')),
              onTap: () {
                _pickMedia(ImageSource.camera, isVideo: true);
                Navigator.of(context).pop();
              },
            ),
            ListTile(
              leading: Icon(Icons.video_library),
              title: Text(AppTranslations.get('video_library')),
              onTap: () {
                _pickMedia(ImageSource.gallery, isVideo: true);
                Navigator.of(context).pop();
              },
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: Text(AppTranslations.get('new_complaint'), style: TextStyle(fontWeight: FontWeight.bold, letterSpacing: 1.2)),
        elevation: 0,
      ),
      body: AnimatedBackground(
        child: _isLoading && !_isUploading
          ? Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: EdgeInsets.all(24),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Modern Image Picker Widget
                    GestureDetector(
                      onTap: _showImageSourceDialog,
                      child: Container(
                        height: 200,
                        decoration: BoxDecoration(
                          color: Colors.grey[50],
                          border: Border.all(color: Colors.teal[200]!, width: 2, style: BorderStyle.solid),
                          borderRadius: BorderRadius.circular(16),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withOpacity(0.05),
                              blurRadius: 10,
                              offset: Offset(0, 4),
                            )
                          ]
                        ),
                        child: _mediaFiles.isNotEmpty
                            ? ListView.builder(
                                scrollDirection: Axis.horizontal,
                                itemCount: _mediaFiles.length,
                                itemBuilder: (context, index) {
                                  final file = _mediaFiles[index];
                                  final isVideo = file.path.endsWith('.mp4') || file.path.endsWith('.mov') || file.path.endsWith('.avi');
                                  return Stack(
                                    children: [
                                      Container(
                                        width: 150,
                                        margin: EdgeInsets.all(8),
                                        decoration: BoxDecoration(
                                          borderRadius: BorderRadius.circular(12),
                                          boxShadow: [
                                            BoxShadow(color: Colors.black12, blurRadius: 4, offset: Offset(2, 2))
                                          ]
                                        ),
                                        child: ClipRRect(
                                          borderRadius: BorderRadius.circular(12),
                                          child: isVideo
                                              ? Container(
                                                  color: Colors.black87,
                                                  child: Center(child: Icon(Icons.play_circle_fill, color: Colors.white, size: 50)),
                                                )
                                              : Image.file(file, fit: BoxFit.cover),
                                        ),
                                      ),
                                      Positioned(
                                        top: 0, right: 0,
                                        child: GestureDetector(
                                          onTap: () => setState(() => _mediaFiles.removeAt(index)),
                                          child: CircleAvatar(
                                            radius: 14,
                                            backgroundColor: Colors.redAccent,
                                            child: Icon(Icons.close, size: 16, color: Colors.white),
                                          ),
                                        ),
                                      ),
                                    ],
                                  );
                                },
                              )
                            : Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.add_a_photo, size: 48, color: Colors.teal[300]),
                                  SizedBox(height: 12),
                                  Text(AppTranslations.get('tap_to_add_photos_or_video'), style: TextStyle(color: Colors.teal[600], fontWeight: FontWeight.w600)),
                                ],
                              ),
                      ),
                    ),
                    SizedBox(height: 30),
                    
                    TextFormField(
                      decoration: InputDecoration(
                        labelText: AppTranslations.get('title_subject'),
                        filled: true,
                        fillColor: Colors.grey[50],
                      ),
                      validator: (value) => value!.isEmpty ? AppTranslations.get('required') : null,
                      onSaved: (value) => _title = value!,
                    ),
                    SizedBox(height: 20),
                    
                    TextFormField(
                      decoration: InputDecoration(
                        labelText: AppTranslations.get('description_details'),
                        filled: true,
                        fillColor: Colors.grey[50],
                      ),
                      maxLines: 4,
                      validator: (value) => value!.isEmpty ? AppTranslations.get('required') : null,
                      onSaved: (value) => _details = value!,
                    ),
                    SizedBox(height: 20),

                    // Map Section
                    Text(AppTranslations.get('complaint_location'), style: TextStyle(fontWeight: FontWeight.bold, color: Colors.teal[800])),
                    SizedBox(height: 8),
                    Container(
                      height: 200,
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.grey.shade300),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: _selectedLat == null || _selectedLng == null
                        ? Center(child: CircularProgressIndicator())
                        : FlutterMap(
                            mapController: _mapController,
                            options: MapOptions(
                              initialCenter: LatLng(_selectedLat!, _selectedLng!),
                              initialZoom: 15.0,
                              onTap: (tapPosition, point) {
                                setState(() {
                                  _selectedLat = point.latitude;
                                  _selectedLng = point.longitude;
                                });
                              },
                            ),
                            children: [
                              TileLayer(
                                urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                                userAgentPackageName: 'com.example.cleancity',
                              ),
                              MarkerLayer(
                                markers: [
                                  Marker(
                                    point: LatLng(_selectedLat!, _selectedLng!),
                                    width: 40,
                                    height: 40,
                                    child: Icon(
                                      Icons.location_on,
                                      color: Colors.red,
                                      size: 40,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                          ),
                    ),
                    SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton.icon(
                        icon: Icon(Icons.my_location, size: 18),
                        label: Text(AppTranslations.get('use_current_location')),
                        onPressed: () async {
                          Position? pos = await _determinePosition();
                          if (pos != null && mounted) {
                            setState(() {
                              _selectedLat = pos.latitude;
                              _selectedLng = pos.longitude;
                            });
                            _mapController.move(LatLng(pos.latitude, pos.longitude), 15.0);
                          }
                        },
                      ),
                    ),
                    SizedBox(height: 20),

                    DropdownButtonFormField<String>(
                      decoration: InputDecoration(
                        labelText: AppTranslations.get('city'),
                        filled: true,
                        fillColor: Colors.grey[50],
                      ),
                      value: _city,
                      items: _cities.map((String value) {
                        return DropdownMenuItem<String>(value: value, child: Text(value));
                      }).toList(),
                      onChanged: (newValue) => setState(() => _city = newValue!),
                    ),
                    SizedBox(height: 20),

                    TextFormField(
                      decoration: InputDecoration(
                        labelText: AppTranslations.get('street_address'),
                        filled: true,
                        fillColor: Colors.grey[50],
                      ),
                      validator: (value) => value!.isEmpty ? AppTranslations.get('required') : null,
                      onSaved: (value) => _address = value!,
                    ),
                    SizedBox(height: 20),

                    TextFormField(
                      decoration: InputDecoration(
                        labelText: AppTranslations.get('nearest_landmark'),
                        filled: true,
                        fillColor: Colors.grey[50],
                      ),
                      validator: (value) => value!.isEmpty ? AppTranslations.get('required') : null,
                      onSaved: (value) => _landmark = value!,
                    ),
                    SizedBox(height: 30),

                    if (_isUploading) ...[
                      Text(AppTranslations.get('uploading_to_buffer_'), style: TextStyle(fontWeight: FontWeight.bold, color: Colors.teal)),
                      SizedBox(height: 8),
                      LinearProgressIndicator(
                        value: _uploadProgress,
                        minHeight: 10,
                        backgroundColor: Colors.teal[100],
                        valueColor: AlwaysStoppedAnimation<Color>(Colors.teal),
                        borderRadius: BorderRadius.circular(5),
                      ),
                      SizedBox(height: 8),
                      Text('${(_uploadProgress * 100).toStringAsFixed(1)}${AppTranslations.get('_completed')}', textAlign: TextAlign.right, style: TextStyle(color: Colors.grey[700])),
                      SizedBox(height: 20),
                    ] else
                      ElevatedButton(
                        onPressed: _submit,
                        child: Text(AppTranslations.get('submit_complaint'), style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 1.1)),
                        style: ElevatedButton.styleFrom(
                          padding: EdgeInsets.symmetric(vertical: 18),
                          backgroundColor: Colors.teal,
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                          elevation: 3,
                        ),
                      ),
                  ],
                ),
              ),
            ),
      ),
    );
  }
}
