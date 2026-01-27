cmake_minimum_required(VERSION 3.8)
project(pharmacy_verification)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(ros_gz_interfaces REQUIRED)

# Find ZBar library
find_library(ZBAR_LIB zbar)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/BarcodeData.msg"
  DEPENDENCIES geometry_msgs
)

# Include directories
include_directories(include)

# Define nodes to build
# Creating executable targets for the lifecycle nodes
set(nodes 
  sim_bridge 
  vision_manager 
  barcode_node 
  ocr_node 
  db_interface 
  conveyor_ctrl 
  robot_controller
  bottle_spawner
)

foreach(node ${nodes})
  add_executable(${node} src/${node}.cpp)
  ament_target_dependencies(${node}
    rclcpp
    rclcpp_lifecycle
    sensor_msgs
    geometry_msgs
    cv_bridge
    ros_gz_interfaces
  )
  if(${node} STREQUAL "barcode_node")
    rosidl_target_interfaces(${node} ${PROJECT_NAME} "rosidl_typesupport_cpp")
    target_link_libraries(${node} ${ZBAR_LIB})
  endif()
  
  install(TARGETS ${node}
    DESTINATION lib/${PROJECT_NAME})
endforeach()

install(
  DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
