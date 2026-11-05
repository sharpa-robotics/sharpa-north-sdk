#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "NorthSDK::NorthSDK" for configuration "Release"
set_property(TARGET NorthSDK::NorthSDK APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(NorthSDK::NorthSDK PROPERTIES
  IMPORTED_LINK_DEPENDENT_LIBRARIES_RELEASE "__zenohc_shared"
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libnorth_sdk.so.1.2.0"
  IMPORTED_SONAME_RELEASE "libnorth_sdk.so.3"
  )

list(APPEND _cmake_import_check_targets NorthSDK::NorthSDK )
list(APPEND _cmake_import_check_files_for_NorthSDK::NorthSDK "${_IMPORT_PREFIX}/lib/libnorth_sdk.so.1.2.0" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
