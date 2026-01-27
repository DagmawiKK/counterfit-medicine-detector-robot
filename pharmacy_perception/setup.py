from setuptools import setup

package_name = "pharmacy_perception"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml", "README.md"]),
        (f"share/{package_name}/launch", ["launch/perception.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Your Name",
    maintainer_email="you@example.com",
    description="Perception nodes for barcode and OCR in the counterfeit medicine detector.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "barcode_node = pharmacy_perception.barcode_node:main",
            "ocr_node = pharmacy_perception.ocr_node:main",
        ],
    },
)
