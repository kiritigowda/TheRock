
##############################################################################
# rocdecode library
##############################################################################

therock_cmake_subproject_declare(rocdecode
    USE_DIST_AMDGPU_TARGETS
    BACKGROUND_BUILD
    EXCLUDE_FROM_ALL
    NO_MERGE_COMPILE_COMMANDS
    OUTPUT_ON_FAILURE
    EXTERNAL_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/rocdecode"
    BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/rocdecode"
    RUNTIME_DEPS
      rocprofiler-register
    BUILD_DEPS
      amd-llvm
      ${THEROCK_BUNDLED_LIBDRM}
      ${THEROCK_BUNDLED_LIBVA}
      ${THEROCK_BUNDLED_LIBVADRM}
    CMAKE_ARGS
      -DHIP_PLATFORM=amd
    INTERFACE_LINK_DIRS
      "lib"
    INSTALL_RPATH_DIRS
      "lib;lib/rocm_sysdeps/lib"
    INTERFACE_INSTALL_RPATH_DIRS
      "lib;lib/rocm_sysdeps/lib"
  )
  therock_cmake_subproject_glob_c_sources(rocdecode
    SUBDIRS
      .
  )
  therock_cmake_subproject_provide_package(rocdecode rocdecode lib/cmake/rocdecode)
  therock_cmake_subproject_activate(rocdecode)

  therock_provide_artifact(rocdecode
    DESCRIPTOR artifact-rocdecode.toml
    COMPONENTS
      dbg
      dev
      lib
      test
    SUBPROJECT_DEPS
      rocdecode
)

##############################################################################
# rocjpeg library
##############################################################################

  therock_cmake_subproject_declare(rocjpeg
    USE_DIST_AMDGPU_TARGETS
    BACKGROUND_BUILD
    EXCLUDE_FROM_ALL
    NO_MERGE_COMPILE_COMMANDS
    OUTPUT_ON_FAILURE
    EXTERNAL_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/rocjpeg"
    BINARY_DIR "${CMAKE_CURRENT_BINARY_DIR}/rocjpeg"
    CMAKE_ARGS
      -DHIP_PLATFORM=amd
    RUNTIME_DEPS
      rocprofiler-register
    BUILD_DEPS
      amd-llvm
      ${THEROCK_BUNDLED_LIBDRM}
      ${THEROCK_BUNDLED_LIBVA}
      ${THEROCK_BUNDLED_LIBVADRM}
    CMAKE_ARGS
      -DHIP_PLATFORM=amd
    INTERFACE_LINK_DIRS
      "lib"
    INSTALL_RPATH_DIRS
      "lib;lib/rocm_sysdeps/lib"
    INTERFACE_INSTALL_RPATH_DIRS
      "lib;lib/rocm_sysdeps/lib"
  )
  therock_cmake_subproject_glob_c_sources(rocjpeg
    SUBDIRS
      .
  )
  therock_cmake_subproject_provide_package(rocjpeg rocjpeg lib/cmake/rocjpeg)
  therock_cmake_subproject_activate(rocjpeg)

  therock_provide_artifact(rocjpeg
    DESCRIPTOR artifact-rocjpeg.toml
    COMPONENTS
      dbg
      dev
      lib
      test
    SUBPROJECT_DEPS
      rocjpeg
  )

endif(THEROCK_ENABLE_SYSDEPS_AMD_MESA)
