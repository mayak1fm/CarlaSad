std_msgs/Header header
uint32 id
string type_id
string role_name
geometry_msgs/Pose pose
geometry_msgs/Twist twist
int32 terrain_label_id    # 100-114 CarlaSad terrain classes
float32 terrain_risk      # 0.0=safe, 1.0=impassable
bool is_in_worked_area
