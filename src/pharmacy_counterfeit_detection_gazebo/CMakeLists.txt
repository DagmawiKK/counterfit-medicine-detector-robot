cmake_minimum_required(VERSION 3.8)
project(pharmacy_counterfeit_detection_gazebo)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-style=mozilla -Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)

install(
  DIRECTORY worlds models launch
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
