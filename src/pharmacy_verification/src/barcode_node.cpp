#include <memory>
#include <string>
#include <vector>

#include "rclcpp/rclcpp.hpp"
#include "rclcpp_lifecycle/lifecycle_node.hpp"
#include "lifecycle_msgs/msg/state.hpp"
#include "cv_bridge/cv_bridge.h"
#include "sensor_msgs/msg/image.hpp"
#include "geometry_msgs/msg/polygon.hpp"
#include "geometry_msgs/msg/point32.hpp"
#include "pharmacy_verification/msg/barcode_data.hpp"

// OpenCV and ZBar
#include <opencv2/opencv.hpp>
#include <opencv2/imgproc/imgproc.hpp>
#include <zbar.h>

using rclcpp_lifecycle::node_interfaces::LifecycleNodeInterface;

class BarcodeNode : public rclcpp_lifecycle::LifecycleNode
{
public:
  BarcodeNode()
  : LifecycleNode("barcode_node"),
    zbar_scanner_()
  {
    // Initialize ZBar scanner
    zbar_scanner_.set_config(zbar::ZBAR_NONE, zbar::ZBAR_CFG_ENABLE, 1);
  }

  LifecycleNodeInterface::CallbackReturn on_configure(const rclcpp_lifecycle::State &)
  {
    RCLCPP_INFO(get_logger(), "Configuring BarcodeNode");
    
    // Publisher
    publisher_ = this->create_publisher<pharmacy_verification::msg::BarcodeData>("/barcode/data", 10);
    
    // Subscriber
    subscriber_ = this->create_subscription<sensor_msgs::msg::Image>(
      "/camera/image_raw", 
      10, 
      std::bind(&BarcodeNode::image_callback, this, std::placeholders::_1)
    );

    return LifecycleNodeInterface::CallbackReturn::SUCCESS;
  }

  LifecycleNodeInterface::CallbackReturn on_activate(const rclcpp_lifecycle::State &)
  {
    RCLCPP_INFO(get_logger(), "Activating BarcodeNode");
    publisher_->on_activate();
    return LifecycleNodeInterface::CallbackReturn::SUCCESS;
  }

  LifecycleNodeInterface::CallbackReturn on_deactivate(const rclcpp_lifecycle::State &)
  {
    RCLCPP_INFO(get_logger(), "Deactivating BarcodeNode");
    publisher_->on_deactivate();
    return LifecycleNodeInterface::CallbackReturn::SUCCESS;
  }

  LifecycleNodeInterface::CallbackReturn on_cleanup(const rclcpp_lifecycle::State &)
  {
    RCLCPP_INFO(get_logger(), "Cleaning up BarcodeNode");
    publisher_.reset();
    subscriber_.reset();
    return LifecycleNodeInterface::CallbackReturn::SUCCESS;
  }

  LifecycleNodeInterface::CallbackReturn on_shutdown(const rclcpp_lifecycle::State &)
  {
    RCLCPP_INFO(get_logger(), "Shutting down BarcodeNode");
    return LifecycleNodeInterface::CallbackReturn::SUCCESS;
  }

private:
  void image_callback(const sensor_msgs::msg::Image::SharedPtr msg)
  {
    if (this->get_current_state().id() != lifecycle_msgs::msg::State::PRIMARY_STATE_ACTIVE) {
      return;
    }

    // 1. Convert ROS image to OpenCV
    cv_bridge::CvImagePtr cv_ptr;
    try {
      cv_ptr = cv_bridge::toCvCopy(msg, sensor_msgs::image_encodings::BGR8);
    } catch (cv_bridge::Exception & e) {
      RCLCPP_ERROR(get_logger(), "cv_bridge exception: %s", e.what());
      return;
    }

    cv::Mat frame = cv_ptr->image;
    cv::Mat gray;
    cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);

    // 2. Pre-processing for Glare/Noise
    // CLAHE (Contrast Limited Adaptive Histogram Equalization) to handle lighting variations/glare
    auto clahe = cv::createCLAHE(2.0, cv::Size(8, 8));
    clahe->apply(gray, gray);

    // Mild Gaussian blur to reduce high-frequency simulation noise
    cv::GaussianBlur(gray, gray, cv::Size(3, 3), 0);
    
    // Sharpening can sometimes help with barcode edges on curved surfaces
    cv::Mat sharpened;
    cv::addWeighted(gray, 1.5, gray, -0.5, 0, sharpened);

    // 3. Wrap image data in a zbar::Image
    int width = gray.cols;
    int height = gray.rows;
    uchar * raw = (uchar *)gray.data;
    
    zbar::Image image(width, height, "Y800", raw, width * height);

    // 4. Scan the image for barcodes
    int n = zbar_scanner_.scan(image);
    (void)n;

    // 5. Process results
    for (zbar::Image::SymbolIterator symbol = image.symbol_begin(); symbol != image.symbol_end(); ++symbol) {
      // Filter for GS1 DataMatrix (ZBAR_DATABAR/ZBAR_DATABAR_EXP) or EAN-13
      // ZBar types: EAN13, DATABAR, DATABAR_EXP, QRCODE, etc.
      // We process all found barcodes for now.
      
      std::string data = symbol->get_data();
      std::string type = symbol->get_type_name(); // e.g., EAN-13, DATEBAR
      
      RCLCPP_INFO(get_logger(), "Detected %s: %s", type.c_str(), data.c_str());

      // Create message
      pharmacy_verification::msg::BarcodeData output_msg;
      output_msg.data = data;
      
      // Polygon
      output_msg.bounding_box.points.clear();
      if (symbol->get_location_size() == 4) {
         for(int i=0; i<4; i++) {
             geometry_msgs::msg::Point32 pt;
             pt.x = static_cast<float>(symbol->get_location_x(i));
             pt.y = static_cast<float>(symbol->get_location_y(i));
             pt.z = 0.0; 
             output_msg.bounding_box.points.push_back(pt);
         }
      }

      publisher_->publish(output_msg);
    }
  }

  // ...existing code...
  // Members
  rclcpp_lifecycle::LifecyclePublisher<pharmacy_verification::msg::BarcodeData>::SharedPtr publisher_;
  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr subscriber_;
  zbar::ImageScanner zbar_scanner_;
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<BarcodeNode>();
  rclcpp::spin(node->get_node_base_interface());
  rclcpp::shutdown();
  return 0;
}
