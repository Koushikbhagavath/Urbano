import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../utils/translations.dart';
import '../../utils/translation_helper.dart';

import '../../services/api_service.dart';
import 'profile_drawer.dart';
import '../complaint/new_complaint_screen.dart';
import '../complaint/complaint_detail_screen.dart';
import '../../widgets/animated_background.dart';

class HomeScreen extends StatefulWidget {
  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  Map<String, dynamic>? _userProfile;
  List<dynamic> _complaints = [];
  bool _isLoading = true;
  bool _isTranslating = false;
  bool _isGridView = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }


  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    
    // Fetch profile and complaints in parallel
    final results = await Future.wait([
      _apiService.getProfile(),
      _apiService.getComplaints(),
    ]);

    final profileRes = results[0];
    final complaintsRes = results[1];

    if (mounted) {
      setState(() {
        if (profileRes['success'] == true) {
          _userProfile = profileRes['profile'];
        }
        if (complaintsRes['success'] == true) {
          _complaints = complaintsRes['complaints'];
        }
        _isLoading = false;
      });
      
      // Do non-blocking background translation and then update state again
      if (complaintsRes['success'] == true && AppTranslations.currentLanguage != 'en') {
        setState(() => _isTranslating = true);
        _translateComplaintsInBackground(_complaints);
      }

      if (!_isProfileComplete() && _userProfile != null) {
        Future.delayed(Duration(milliseconds: 300), () {
          if (mounted) _scaffoldKey.currentState?.openDrawer();
        });
      }
    }
  }

  void _translateComplaintsInBackground(List<dynamic> comps) async {
    List<Future<void>> futures = [];
    for (var i = 0; i < comps.length; i++) {
      futures.add(() async {
         var t = await TranslationHelper.translateText(comps[i]['title'] ?? '');
         var d = await TranslationHelper.translateText(comps[i]['details'] ?? '');
         comps[i]['title'] = t;
         comps[i]['details'] = d;
      }());
    }
    await Future.wait(futures);
    if (mounted) {
      setState(() {
         _complaints = comps;
         _isTranslating = false;
      });
    }
  }

  bool _isProfileComplete() {
    if (_userProfile == null) return false;
    
    String name = _userProfile!['name'] ?? '';
    String mobile = _userProfile!['mobile_number'] ?? '';
    String address = _userProfile!['address'] ?? '';

    if (name == 'New Mobile User' || name.isEmpty) return false;
    if (mobile.startsWith('OTP-') || mobile.isEmpty) return false;
    if (address.isEmpty) return false;

    return true;
  }

  @override
  Widget build(BuildContext context) {
    bool isComplete = _isProfileComplete();

    return Scaffold(
      key: _scaffoldKey,
      appBar: AppBar(
        title: Text(isComplete && _userProfile!['name'].toString().isNotEmpty
            ? '${AppTranslations.get('hello')} ${_userProfile!['name']}'
            : AppTranslations.get('hello_user')),
        actions: [
          
          PopupMenuButton<String>(
            icon: Icon(Icons.language),
            onSelected: (String langCode) async {
              SharedPreferences prefs = await SharedPreferences.getInstance();
              await prefs.setString('app_language', langCode);
              setState(() {
                AppTranslations.currentLanguage = langCode;
              });
              _loadData();
            },
            itemBuilder: (BuildContext context) => <PopupMenuEntry<String>>[
              const PopupMenuItem<String>(value: 'en', child: Text('English')),
              const PopupMenuItem<String>(value: 'kn', child: Text('ಕನ್ನಡ')),
              const PopupMenuItem<String>(value: 'ta', child: Text('தமிழ்')),
              const PopupMenuItem<String>(value: 'ml', child: Text('മലയാളം')),
              const PopupMenuItem<String>(value: 'hi', child: Text('हिन्दी')),
              const PopupMenuItem<String>(value: 'te', child: Text('తెలుగు')),
            ],
          ),
          IconButton(
            icon: Icon(_isGridView ? Icons.view_list_rounded : Icons.grid_view_rounded),
            onPressed: () => setState(() => _isGridView = !_isGridView),
          )
        ],
      ),
      backgroundColor: Color(0xFFF0F4F8),
      drawer: _userProfile != null 
          ? ProfileDrawer(
              initialProfile: _userProfile,
              onProfileUpdated: _loadData,
            )
          : null,
      body: AnimatedBackground(
        child: _isLoading
            ? Center(child: CircularProgressIndicator(color: Colors.teal))
            : Column(
                children: [
                  if (_isTranslating)
                    Container(
                      width: double.infinity,
                      color: Colors.teal.shade50,
                      padding: EdgeInsets.symmetric(vertical: 4),
                      child: Center(
                        child: Text(AppTranslations.get('loading'), style: TextStyle(color: Colors.teal, fontSize: 12)),
                      ),
                    ),
                  Expanded(
                    child: RefreshIndicator(
                      onRefresh: _loadData,
                child: Column(
                  children: [
                    if (!isComplete)
                      Container(
                        color: Colors.orange[100],
                        padding: EdgeInsets.all(12),
                        child: Row(
                          children: [
                            Icon(Icons.warning, color: Colors.orange[800]),
                            SizedBox(width: 10),
                            Expanded(
                              child: Text(AppTranslations.get('please_complete_your_profile_in_the_sidebar_menu_to_submit_complaints'),
                                style: TextStyle(color: Colors.orange[900]),
                              ),
                            ),
                          ],
                        ),
                      ),
                    Expanded(
                      child: _complaints.isEmpty
                          ? ListView(
                              physics: AlwaysScrollableScrollPhysics(),
                              children: [
                                SizedBox(height: MediaQuery.of(context).size.height * 0.3),
                                Center(
                                  child: Text(
                                    AppTranslations.get('no_complaints_yet_n_tap_to_create_one_'),
                                    textAlign: TextAlign.center,
                                    style: TextStyle(color: Colors.grey, fontSize: 16),
                                  ),
                                ),
                              ],
                            )
                          : _isGridView 
                              ? GridView.builder(
                                  physics: AlwaysScrollableScrollPhysics(),
                                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                                    crossAxisCount: 2,
                                    childAspectRatio: 0.85,
                                  ),
                                  itemCount: _complaints.length,
                                  itemBuilder: (context, index) {
                                    var complaint = _complaints[index];
                                    Color statusColor = Colors.orange;
                                    IconData statusIcon = Icons.access_time;
                                    if (complaint['status'] == 'Resolved') {
                                      statusColor = Colors.teal;
                                      statusIcon = Icons.check_circle;
                                    } else if (complaint['status'] == 'Registered') {
                                      statusColor = Colors.blueAccent;
                                      statusIcon = Icons.app_registration;
                                    }
                                    return _buildGridCard(complaint, statusColor, statusIcon);
                                  },
                                )
                              : ListView.builder(
                                  physics: AlwaysScrollableScrollPhysics(),
                                  itemCount: _complaints.length,
                                  itemBuilder: (context, index) {
                                    var complaint = _complaints[index];
                                    Color statusColor = Colors.orange;
                                    IconData statusIcon = Icons.access_time;
                                    if (complaint['status'] == 'Resolved') {
                                      statusColor = Colors.teal;
                                      statusIcon = Icons.check_circle;
                                    } else if (complaint['status'] == 'Registered') {
                                      statusColor = Colors.blueAccent;
                                      statusIcon = Icons.app_registration;
                                    }
                                    return _buildListCard(complaint, statusColor, statusIcon);
                                  },
                                ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: (!isComplete || _isLoading)
          ? null
          : FloatingActionButton(
        onPressed: isComplete 
          ? () async {
              // Navigate to New Complaint Screen and reload data upon return
              final result = await Navigator.push(
                context,
                MaterialPageRoute(builder: (context) => NewComplaintScreen()),
              );
              if (result == true) {
                _loadData();
              }
            } 
          : () {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text(AppTranslations.get('please_complete_your_profile_first_'))),
              );
              // Open Drawer
              _scaffoldKey.currentState?.openDrawer();
            },
        child: Icon(Icons.add),
        backgroundColor: isComplete ? Colors.green : Colors.grey,
      ),
    );
  }

  Widget _buildListCard(Map<String, dynamic> complaint, Color statusColor, IconData statusIcon) {
    return Container(
      margin: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 10, offset: Offset(0, 4))
        ],
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () async {
          await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => ComplaintDetailScreen(complaint: complaint),
            ),
          );
          _loadData();
        },
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(statusIcon, color: statusColor, size: 28),
              ),
              SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: Text(
                            complaint['title'],
                            style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: Colors.grey[800]),
                            maxLines: 1, overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        Text(
                          complaint['created_at'].toString().substring(0, 10),
                          style: TextStyle(fontSize: 12, color: Colors.grey[500], fontWeight: FontWeight.w500),
                        ),
                      ],
                    ),
                    SizedBox(height: 6),
                    Row(
                      children: [
                        Icon(Icons.location_on, size: 14, color: Colors.grey[400]),
                        SizedBox(width: 4),
                        Text(
                          complaint['city'],
                          style: TextStyle(color: Colors.grey[600], fontSize: 13),
                        ),
                      ],
                    ),
                    SizedBox(height: 12),
                    Container(
                      padding: EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: statusColor.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: statusColor.withOpacity(0.5)),
                      ),
                      child: Text(
                        AppTranslations.get(complaint['status'].toString().toLowerCase()).toUpperCase(),
                        style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                      ),
                    )
                  ],
                ),
              )
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildGridCard(Map<String, dynamic> complaint, Color statusColor, IconData statusIcon) {
    return Container(
      margin: EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 10, offset: Offset(0, 4))
        ],
        border: Border.all(color: Colors.grey.shade200),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: () async {
          await Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => ComplaintDetailScreen(complaint: complaint),
            ),
          );
          _loadData();
        },
        child: Padding(
          padding: EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Container(
                    padding: EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: statusColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(statusIcon, color: statusColor, size: 24),
                  ),
                  Text(
                    complaint['created_at'].toString().substring(0, 10),
                    style: TextStyle(fontSize: 11, color: Colors.grey[500], fontWeight: FontWeight.w500),
                  ),
                ],
              ),
              Spacer(),
              Text(
                complaint['title'],
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15, color: Colors.grey[800]),
                maxLines: 2, overflow: TextOverflow.ellipsis,
              ),
              SizedBox(height: 8),
              Row(
                children: [
                  Icon(Icons.location_on, size: 12, color: Colors.grey[400]),
                  SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      complaint['city'],
                      style: TextStyle(color: Colors.grey[600], fontSize: 12),
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              SizedBox(height: 12),
              Container(
                padding: EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: statusColor.withOpacity(0.5)),
                ),
                child: Text(
                  AppTranslations.get(complaint['status'].toString().toLowerCase()).toUpperCase(),
                  style: TextStyle(color: statusColor, fontSize: 9, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                ),
              )
            ],
          ),
        ),
      ),
    );
  }
}
