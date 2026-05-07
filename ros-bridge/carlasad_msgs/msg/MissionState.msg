std_msgs/Header header

# States: 0=idle 1=running 2=paused 3=completed 4=error
uint8 IDLE=0
uint8 RUNNING=1
uint8 PAUSED=2
uint8 COMPLETED=3
uint8 ERROR=4

uint8 state
string mission_id
float32 progress          # 0.0-1.0
float32 elapsed_seconds
string logging_mode
string world_mode
string map_name
