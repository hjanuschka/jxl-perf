cmake_minimum_required(VERSION 3.10)
project(jxl_benchmarks)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(JXL REQUIRED libjxl)
pkg_check_modules(PNG REQUIRED libpng)

add_executable(test_decode_cxx test_decode_cxx.cpp)
target_include_directories(test_decode_cxx PRIVATE ${JXL_INCLUDE_DIRS} ${PNG_INCLUDE_DIRS})
target_link_libraries(test_decode_cxx ${JXL_LIBRARIES} ${PNG_LIBRARIES})
