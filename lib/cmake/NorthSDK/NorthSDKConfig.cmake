
####### Expanded from @PACKAGE_INIT@ by configure_package_config_file() #######
####### Any changes to this file will be overwritten by the next CMake run ####
####### The input file was NorthSDKConfig.cmake.in                            ########

get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../" ABSOLUTE)

macro(set_and_check _var _file)
  set(${_var} "${_file}")
  if(NOT EXISTS "${_file}")
    message(FATAL_ERROR "File or directory ${_file} referenced by variable ${_var} does not exist !")
  endif()
endmacro()

macro(check_required_components _NAME)
  foreach(comp ${${_NAME}_FIND_COMPONENTS})
    if(NOT ${_NAME}_${comp}_FOUND)
      if(${_NAME}_FIND_REQUIRED_${comp})
        set(${_NAME}_FOUND FALSE)
      endif()
    endif()
  endforeach()
endmacro()

####################################################################################

set(_NORTHSDK_RUNTIME_LIBDIR "${PACKAGE_PREFIX_DIR}/lib")
set(_NORTHSDK_RUNTIME_TARGETS "")

if(EXISTS "${_NORTHSDK_RUNTIME_LIBDIR}/libprotobuf.so")
  if(NOT TARGET NorthSDK::protobuf_runtime)
    add_library(NorthSDK::protobuf_runtime SHARED IMPORTED)
    set_target_properties(NorthSDK::protobuf_runtime PROPERTIES
      IMPORTED_LOCATION "${_NORTHSDK_RUNTIME_LIBDIR}/libprotobuf.so")
  endif()
  list(APPEND _NORTHSDK_RUNTIME_TARGETS NorthSDK::protobuf_runtime)
endif()

if(EXISTS "${_NORTHSDK_RUNTIME_LIBDIR}/libzenohc.so")
  if(NOT TARGET NorthSDK::zenoh_runtime)
    add_library(NorthSDK::zenoh_runtime SHARED IMPORTED)
    set_target_properties(NorthSDK::zenoh_runtime PROPERTIES
      IMPORTED_LOCATION "${_NORTHSDK_RUNTIME_LIBDIR}/libzenohc.so")
  endif()
  list(APPEND _NORTHSDK_RUNTIME_TARGETS NorthSDK::zenoh_runtime)
endif()

include("${CMAKE_CURRENT_LIST_DIR}/NorthSDKTargets.cmake")
if(_NORTHSDK_RUNTIME_TARGETS)
  set_property(TARGET NorthSDK::NorthSDK APPEND PROPERTY
    INTERFACE_LINK_LIBRARIES "${_NORTHSDK_RUNTIME_TARGETS}")
endif()

check_required_components(NorthSDK)
