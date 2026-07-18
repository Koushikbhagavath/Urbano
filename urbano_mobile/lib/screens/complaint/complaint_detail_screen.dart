import 'package:flutter/material.dart';
import '../../utils/translations.dart';

import 'package:cached_network_image/cached_network_image.dart';
import 'dart:io';
import '../../utils/constants.dart';
import 'package:intl/intl.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:video_player/video_player.dart';
import 'package:chewie/chewie.dart';
import '../../widgets/animated_background.dart';

class ComplaintDetailScreen extends StatelessWidget {
  final Map<String, dynamic> complaint;

  ComplaintDetailScreen({required this.complaint});

  @override
  Widget build(BuildContext context) {
    List<dynamic> history = complaint['history'] ?? [];
    List<dynamic> media = complaint['media'] ?? [];

    return Scaffold(
      appBar: AppBar(
        title: Text(AppTranslations.get('complaint_details')),
      ),
      body: AnimatedBackground(
        child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Display Image/Media if available
            if (media.isNotEmpty)
              Container(
                height: 250,
                child: ListView.builder(
                  scrollDirection: Axis.horizontal,
                  itemCount: media.length,
                  itemBuilder: (context, index) {
                    final isVideo = media[index].toString().toLowerCase().endsWith('.mp4');
                    return Container(
                      width: MediaQuery.of(context).size.width,
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          if (isVideo)
                            InlineVideoPlayer(url: '${AppConstants.baseUrl.replaceAll('/api', '')}/${media[index]}')
                          else
                            CachedNetworkImage(
                              imageUrl: '${AppConstants.baseUrl.replaceAll('/api', '')}/${media[index]}',
                              fit: BoxFit.contain,
                              placeholder: (context, url) => Center(child: CircularProgressIndicator()),
                              errorWidget: (context, url, error) => 
                                Container(
                                  color: Colors.grey[200],
                                  child: Icon(Icons.broken_image, size: 50, color: Colors.grey[400]),
                                ),
                            ),
                          if (media.length > 1)
                            Positioned(
                              bottom: 10,
                              right: 10,
                              child: Container(
                                padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: Colors.black54,
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Text(
                                  '${index + 1} / ${media.length}',
                                  style: TextStyle(color: Colors.white, fontSize: 12),
                                ),
                              ),
                            ),
                        ],
                      ),
                    );
                  },
                ),
              )
            else
              Container(
                height: 150,
                color: Colors.grey[100],
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.image_not_supported, size: 40, color: Colors.grey[400]),
                      SizedBox(height: 8),
                      Text(AppTranslations.get('no_media_attached'), style: TextStyle(color: Colors.grey[500])),
                    ],
                  ),
                ),
              ),

            Padding(
              padding: EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Title and Status
                  Text(
                    '${AppTranslations.get('complaint')} #${complaint['id'] ?? 'N/A'}',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: Colors.teal, letterSpacing: 1.0),
                  ),
                  SizedBox(height: 6),
                  Text(
                    complaint['title'],
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: Colors.grey[800], letterSpacing: -0.5),
                  ),
                  SizedBox(height: 12),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      Flexible(
                        child: Container(
                          padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                          decoration: BoxDecoration(
                            color: complaint['status'] == 'Resolved' ? Colors.teal.withOpacity(0.1) : Colors.orange.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(color: complaint['status'] == 'Resolved' ? Colors.teal : Colors.orange),
                          ),
                          child: Text(
                            AppTranslations.get(complaint['status'].toString().toLowerCase()).toUpperCase(),
                            style: TextStyle(
                              color: complaint['status'] == 'Resolved' ? Colors.teal : Colors.orange, 
                              fontWeight: FontWeight.w800,
                              fontSize: 12,
                              letterSpacing: 0.5
                            ),
                          ),
                        ),
                      ),
                      SizedBox(width: 16),
                      Text(
                        complaint['created_at']?.toString().substring(0, 10) ?? AppTranslations.get('date_n_a'),
                        style: TextStyle(fontSize: 12, color: Colors.grey[500], fontWeight: FontWeight.w600),
                      ),
                    ],
                  ),
                  SizedBox(height: 16),

                  // Location info
                  Row(
                    children: [
                      Icon(Icons.location_on, color: Colors.grey[400], size: 18),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          '${complaint['address']}, ${complaint['landmark']}, ${complaint['city']}',
                          style: TextStyle(color: Colors.grey[600], fontSize: 14, height: 1.4),
                        ),
                      ),
                    ],
                  ),
                  SizedBox(height: 16),
                  
                  // Interactive Map
                  if (complaint['latitude'] != null && complaint['longitude'] != null) ...[
                    Container(
                      height: 200,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: Colors.grey.shade300),
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: FlutterMap(
                        options: MapOptions(
                          initialCenter: LatLng(
                            double.tryParse(complaint['latitude']?.toString() ?? '0') ?? 0.0,
                            double.tryParse(complaint['longitude']?.toString() ?? '0') ?? 0.0,
                          ),
                          initialZoom: 15.0,
                        ),
                        children: [
                          TileLayer(
                            urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                            userAgentPackageName: 'com.example.cleancity',
                          ),
                          MarkerLayer(
                            markers: [
                              Marker(
                                point: LatLng(
                                  double.tryParse(complaint['latitude']?.toString() ?? '0') ?? 0.0,
                                  double.tryParse(complaint['longitude']?.toString() ?? '0') ?? 0.0,
                                ),
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
                    SizedBox(height: 30),
                  ],

                  // Details Description
                  Text(AppTranslations.get('description'), style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.teal[800])),
                  SizedBox(height: 8),
                  Container(
                    padding: EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.grey[50],
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: Colors.grey.shade200),
                    ),
                    child: Text(
                      complaint['details'],
                      style: TextStyle(fontSize: 15, height: 1.6, color: Colors.grey[700]),
                    ),
                  ),
                  
                  SizedBox(height: 30),

                  // History Timeline
                  Text(AppTranslations.get('timeline'), style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.teal[800])),
                  SizedBox(height: 20),

                  if (history.isEmpty)
                    Text(AppTranslations.get('no_status_history_available_'), style: TextStyle(color: Colors.grey)),
                  
                  ...history.map((event) {
                    DateTime timestamp;
                    try {
                      timestamp = HttpDate.parse(event['created_at'] ?? event['timestamp'] ?? '');
                    } catch (e) {
                      timestamp = DateTime.tryParse(event['created_at'] ?? event['timestamp'] ?? '') ?? DateTime.now();
                    }
                    String formattedDate = DateFormat('MMM d, yyyy - h:mm a').format(timestamp);

                    dynamic noteValue = event['note'] ?? event['manual_note'];
                    bool isLast = history.last == event;

                    return IntrinsicHeight(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Column(
                            children: [
                              Container(
                                width: 16,
                                height: 16,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: Colors.teal,
                                  border: Border.all(color: Colors.teal.shade100, width: 4),
                                ),
                              ),
                              if (!isLast)
                                Expanded(
                                  child: Container(
                                    width: 2,
                                    color: Colors.teal.withOpacity(0.2),
                                  ),
                                ),
                            ],
                          ),
                          SizedBox(width: 20),
                          Expanded(
                            child: Padding(
                              padding: const EdgeInsets.only(bottom: 24.0),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    event['action_type'],
                                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: Colors.grey[800]),
                                  ),
                                  SizedBox(height: 4),
                                  Text(
                                    '${AppTranslations.get('by')} ${event['updated_by_role']} ${AppTranslations.get('on')} $formattedDate',
                                    style: TextStyle(color: Colors.grey[500], fontSize: 13, fontWeight: FontWeight.w500),
                                  ),
                                  if (noteValue != null && noteValue.toString().isNotEmpty)
                                    Container(
                                      margin: const EdgeInsets.only(top: 8.0),
                                      padding: EdgeInsets.all(12),
                                      decoration: BoxDecoration(
                                        color: Colors.teal.withOpacity(0.05),
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Text(
                                        noteValue.toString(),
                                        style: TextStyle(fontStyle: FontStyle.italic, color: Colors.teal[800], fontSize: 14),
                                      ),
                                    ),
                                ],
                              ),
                            ),
                          )
                        ],
                      ),
                    );
                  }).toList(),
                ],
              ),
            )
          ],
        ),
      ),
      ),
    );
  }

  Widget _buildInfoRow(IconData icon, String label, String value) {
    return Row(
      children: [
        Icon(icon, size: 20, color: Colors.teal),
        SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: TextStyle(fontSize: 12, color: Colors.grey[500])),
              SizedBox(height: 2),
              Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.grey[800])),
            ],
          ),
        ),
      ],
    );
  }
}

class InlineVideoPlayer extends StatefulWidget {
  final String url;
  InlineVideoPlayer({required this.url});
  @override
  _InlineVideoPlayerState createState() => _InlineVideoPlayerState();
}

class _InlineVideoPlayerState extends State<InlineVideoPlayer> {
  late VideoPlayerController _videoPlayerController;
  ChewieController? _chewieController;

  @override
  void initState() {
    super.initState();
    _initializePlayer();
  }

  Future<void> _initializePlayer() async {
    _videoPlayerController = VideoPlayerController.networkUrl(Uri.parse(widget.url));
    await _videoPlayerController.initialize();
    _videoPlayerController.addListener(() {
      setState(() {});
    });
    setState(() {});
  }

  @override
  void dispose() {
    _videoPlayerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_videoPlayerController.value.isInitialized) {
      return Stack(
        fit: StackFit.expand,
        children: [
          VideoPlayer(_videoPlayerController),
          if (!_videoPlayerController.value.isPlaying)
            Container(
              color: Colors.black26,
              child: Center(
                child: IconButton(
                  icon: Icon(Icons.play_circle_fill, color: Colors.white.withOpacity(0.9), size: 60),
                  onPressed: () {
                    _videoPlayerController.play();
                  },
                ),
              ),
            ),
          if (_videoPlayerController.value.isPlaying)
            GestureDetector(
              onTap: () {
                _videoPlayerController.pause();
              },
              child: Container(color: Colors.transparent),
            ),
        ],
      );
    } else {
      return Container(
        color: Colors.black12,
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              CircularProgressIndicator(color: Colors.teal),
              SizedBox(height: 8),
              Text(AppTranslations.get('loading_video_'), style: TextStyle(color: Colors.teal, fontSize: 12)),
            ],
          ),
        ),
      );
    }
  }
}
