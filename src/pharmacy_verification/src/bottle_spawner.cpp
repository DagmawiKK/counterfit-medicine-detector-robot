#include <chrono>
#include <memory>
#include <random>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "geometry_msgs/msg/twist.hpp"
#include "geometry_msgs/msg/pose.hpp"
#include "ros_gz_interfaces/msg/entity_factory.hpp"
#include "ros_gz_interfaces/msg/entity.hpp"
#include "ros_gz_interfaces/srv/spawn_entity.hpp"
#include "ros_gz_interfaces/srv/set_entity_pose.hpp"

using namespace std::chrono_literals;

class BottleSpawner : public rclcpp::Node
{
public:
  BottleSpawner()
  : Node("bottle_spawner"),
    rng_(std::random_device{}()),
    spawn_count_(0),
    reset_phase_A_(true)
  {
    declare_parameter("spawn_interval_sec", 4.0);
    declare_parameter("belt_velocity", -0.2);
    declare_parameter("spawn_x", 0.0);
    declare_parameter("spawn_y", 0.5);
    declare_parameter("spawn_z", 0.95);
    declare_parameter("spawn_roll", 1.5708);
    declare_parameter("spawn_pitch", 0.0);
    declare_parameter("spawn_yaw", 3.14159);
    declare_parameter("spawn_service", "/create");

    // Four publishers: top run (visible) and return run (hidden)
    belt_pub_A_ = create_publisher<geometry_msgs::msg::Twist>("/model/moving_belt_A/cmd_vel", 10);
    belt_pub_B_ = create_publisher<geometry_msgs::msg::Twist>("/model/moving_belt_B/cmd_vel", 10);
    belt_pub_A_return_ = create_publisher<geometry_msgs::msg::Twist>("/model/moving_belt_A_return/cmd_vel", 10);
    belt_pub_B_return_ = create_publisher<geometry_msgs::msg::Twist>("/model/moving_belt_B_return/cmd_vel", 10);

    auto service_name = get_parameter("spawn_service").as_string();
    spawn_client_ = create_client<ros_gz_interfaces::srv::SpawnEntity>(service_name);

    // Client for resetting belt position (Infinite Loop effect)
    set_pose_client_ = create_client<ros_gz_interfaces::srv::SetEntityPose>("/world/pharmacy_world/set_pose");

    bottle_models_ = {
      "medicine_bottle_v1",
      "medicine_bottle_v2",
      "medicine_bottle_v3",
      "medicine_bottle_v4",
      "medicine_bottle_v5"
    };

    belt_timer_ = create_wall_timer(200ms, std::bind(&BottleSpawner::publish_belt_cmd, this));
    
    spawn_timer_ = create_wall_timer(
      std::chrono::duration<double>(get_parameter("spawn_interval_sec").as_double()),
      std::bind(&BottleSpawner::spawn_bottle, this)
    );

    // Setup Infinite Belt Loop Logic (For Negative Velocity / Moving Left)
    // Belt Length = 2.0m. Velocity = -0.2 m/s. Travel Time = 10.0s.
    // A starts at 0.0. B starts at +2.0.
    // At T=10s: A->-2.0 (Reset to +2.0). B->0.0.
    // At T=20s: A->0.0. B->-2.0 (Reset to +2.0).
    double velocity = get_parameter("belt_velocity").as_double();
    // Use absolute value to determine period, assuming logic handles position
    double period = 2.0 / std::abs(velocity); 
    
    reset_timer_ = create_wall_timer(
      std::chrono::duration<double>(period), 
      std::bind(&BottleSpawner::reset_belt_loop, this));
  }

private:
  void publish_belt_cmd()
  {
    geometry_msgs::msg::Twist cmd;
    cmd.linear.x = get_parameter("belt_velocity").as_double();
    belt_pub_A_->publish(cmd);
    belt_pub_B_->publish(cmd);

    // Return run moves opposite to create the wrap visual
    geometry_msgs::msg::Twist return_cmd;
    return_cmd.linear.x = -cmd.linear.x;
    belt_pub_A_return_->publish(return_cmd);
    belt_pub_B_return_->publish(return_cmd);
  }

  void reset_belt_loop()
  {
      if (!set_pose_client_->service_is_ready()) {
          // If service not ready, we skip this reset. The belt will drift into wall. 
          // Retry logic could be added but simplifed here.
          return;
      }

      auto req = std::make_shared<ros_gz_interfaces::srv::SetEntityPose::Request>();
      
        // Top run reset (moving left, teleport to the right)
        if (reset_phase_A_) {
          req->entity.name = "moving_belt_A";
        } else {
          req->entity.name = "moving_belt_B";
        }
        req->entity.type = ros_gz_interfaces::msg::Entity::MODEL;
        req->pose.position.x = 2.0;
        req->pose.position.y = 0.0;
        req->pose.position.z = 0.815;
        req->pose.orientation.w = 1.0;
        set_pose_client_->async_send_request(req);
        reset_phase_A_ = !reset_phase_A_;

        // Return run reset (moving right, teleport to the left)
        auto req_return = std::make_shared<ros_gz_interfaces::srv::SetEntityPose::Request>();
        if (reset_phase_return_) {
          req_return->entity.name = "moving_belt_A_return";
        } else {
          req_return->entity.name = "moving_belt_B_return";
        }
        req_return->entity.type = ros_gz_interfaces::msg::Entity::MODEL;
        req_return->pose.position.x = -2.0;
        req_return->pose.position.y = 0.0;
        req_return->pose.position.z = 0.68;
        req_return->pose.orientation.w = 1.0;
        set_pose_client_->async_send_request(req_return);
        reset_phase_return_ = !reset_phase_return_;
  }

  geometry_msgs::msg::Pose make_pose(double x, double y, double z, double roll, double pitch, double yaw)
  {
    geometry_msgs::msg::Pose pose;
    pose.position.x = x;
    pose.position.y = y;
    pose.position.z = z;

    const double cy = cos(yaw * 0.5);
    const double sy = sin(yaw * 0.5);
    const double cp = cos(pitch * 0.5);
    const double sp = sin(pitch * 0.5);
    const double cr = cos(roll * 0.5);
    const double sr = sin(roll * 0.5);

    pose.orientation.w = cr * cp * cy + sr * sp * sy;
    pose.orientation.x = sr * cp * cy - cr * sp * sy;
    pose.orientation.y = cr * sp * cy + sr * cp * sy;
    pose.orientation.z = cr * cp * sy - sr * sp * cy;

    return pose;
  }

  void spawn_bottle()
  {
    if (!spawn_client_->wait_for_service(1s)) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 5000, "Spawn service not available yet");
      return;
    }

    std::uniform_int_distribution<size_t> dist(0, bottle_models_.size() - 1);
    const std::string model_name = bottle_models_[dist(rng_)];

    auto request = std::make_shared<ros_gz_interfaces::srv::SpawnEntity::Request>();
    request->entity_factory.name = model_name + std::string("_") + std::to_string(spawn_count_++);
    request->entity_factory.allow_renaming = true;
    request->entity_factory.sdf = build_sdf(model_name);
    request->entity_factory.pose = make_pose(
      get_parameter("spawn_x").as_double(),
      get_parameter("spawn_y").as_double(),
      get_parameter("spawn_z").as_double(),
      get_parameter("spawn_roll").as_double(),
      get_parameter("spawn_pitch").as_double(),
      get_parameter("spawn_yaw").as_double()
    );
    request->entity_factory.relative_to = "world";

    auto future = spawn_client_->async_send_request(request);
  }

  std::string build_sdf(const std::string & model_uri)
  {
    std::string sdf =
      std::string("<sdf version='1.9'>") +
      "<model name='" + model_uri + "'>" +
      "<include><uri>model://" + model_uri + "</uri></include>" +
      "</model></sdf>";
    return sdf;
  }

  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr belt_pub_A_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr belt_pub_B_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr belt_pub_A_return_;
  rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr belt_pub_B_return_;
  rclcpp::Client<ros_gz_interfaces::srv::SpawnEntity>::SharedPtr spawn_client_;
  rclcpp::Client<ros_gz_interfaces::srv::SetEntityPose>::SharedPtr set_pose_client_;

  rclcpp::TimerBase::SharedPtr belt_timer_;
  rclcpp::TimerBase::SharedPtr spawn_timer_;
  rclcpp::TimerBase::SharedPtr reset_timer_;

  std::vector<std::string> bottle_models_;
  std::mt19937 rng_;
  size_t spawn_count_;
  bool reset_phase_A_;
  bool reset_phase_return_ {true};
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<BottleSpawner>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
