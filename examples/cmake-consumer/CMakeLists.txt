cmake_minimum_required(VERSION 3.16)
project(north_sdk_consumer LANGUAGES CXX)

find_package(NorthSDK CONFIG REQUIRED)

add_executable(north_sdk_consumer main.cpp)
target_link_libraries(north_sdk_consumer PRIVATE NorthSDK::NorthSDK)
