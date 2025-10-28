# Copyright (c) 2025 Advanced Micro Devices, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

## AMD Mesa build commands
## export PKG_CONFIG_PATH=build/dist/lib/rocm_sysdeps/lib/pkgconfig
## meson setup build -Damd-decode-only=true --prefix ~/therock-tarball/driver/new_mesa
## ninja -C build install

find_program(MESON_BUILD meson)
if(NOT MESON_BUILD)
  message(FATAL_ERROR "Building with THEROCK_BUNDLE_SYSDEPS=ON on Linux requires (easiest: `pip install meson`)")
endif()

if(NOT CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    set(_source_dir "${CMAKE_CURRENT_BINARY_DIR}/mesa-fork")
    therock_cmake_subproject_declare(therock-mesa
      EXTERNAL_SOURCE_DIR ./mesa-fork
      BINARY_DIR build
      NO_MERGE_COMPILE_COMMANDS
      BACKGROUND_BUILD
      OUTPUT_ON_FAILURE
      CMAKE_ARGS
        "-DSOURCE_DIR=${_source_dir}"
        "-DMESON_BUILD=${MESON_BUILD}"
      INSTALL_DESTINATION
        lib/rocm_sysdeps
      INTERFACE_LINK_DIRS
        lib/rocm_sysdeps/lib
      INTERFACE_INSTALL_RPATH_DIRS
        lib/rocm_sysdeps/lib
      INTERFACE_PKG_CONFIG_DIRS
        lib/rocm_sysdeps/lib/pkgconfig
    )
    therock_cmake_subproject_activate(therock-mesa)

    therock_test_validate_shared_lib(
      PATH build/dist/lib/rocm_sysdeps/lib/x86_64-linux-gnu/dri
      LIB_NAMES radeonsi_drv_video.so libgallium_drv_video.so
    )
    return()
endif()

# Otherwise, this is the sub-project build.
cmake_minimum_required(VERSION 3.25)
project(AMD_MESA_BUILD)

# Meson refuses to build if the source dir is a subdir of the build dir, so
# make it a sibling.
set(PATCH_SOURCE_DIR "${CMAKE_CURRENT_BINARY_DIR}/../patch_source")

add_custom_target(
  meson_build ALL
  WORKING_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}"
  COMMAND
    "${CMAKE_COMMAND}" -E rm -rf -- "${CMAKE_INSTALL_PREFIX}" "${PATCH_SOURCE_DIR}"
  COMMAND
    # We have to patch the sources so make a fresh copy.
    "${CMAKE_COMMAND}" -E copy_directory "${SOURCE_DIR}" "${PATCH_SOURCE_DIR}"
  COMMAND
    # Inline the amdgpu device table.
    "${CMAKE_CURRENT_SOURCE_DIR}/inline_amdgpu_ids.sh" "${PATCH_SOURCE_DIR}"
  COMMAND
    "${CMAKE_COMMAND}" -E chdir "${PATCH_SOURCE_DIR}"
    "${CMAKE_COMMAND}" -E env
      # Escaping hack: experimentally determined to persist through the layers.
      "LDFLAGS=-Wl,-rpath='$$ORIGIN' -Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/version.lds"
      --
      "${MESON_BUILD}" setup "${CMAKE_CURRENT_BINARY_DIR}"
        --reconfigure
        # We generate relocatable, arch neutral directory layouts and use
        # DESTDIR to install int ot the lib/rocm_sysdeps tree.
        --prefix "/"
        -Dpkgconfig.relocatable=true
        -Dlibdir=lib
        # Only enable the libraries we want.
        -Damdgpu=enabled
        -Dintel=disabled
        -Dman-pages=disabled
        -Dnouveau=disabled
        -Dradeon=disabled
        -Dvmwgfx=disabled
  COMMAND
    "${MESON_BUILD}" compile --verbose
  COMMAND
    "${CMAKE_COMMAND}" -E env "DESTDIR=${CMAKE_INSTALL_PREFIX}" --
      "${MESON_BUILD}" install
  COMMAND
    "${CMAKE_COMMAND}" -E env
      "PATCHELF=${PATCHELF}"
      "THEROCK_SOURCE_DIR=${THEROCK_SOURCE_DIR}"
      "Python3_EXECUTABLE=${Python3_EXECUTABLE}" --
    "${CMAKE_CURRENT_SOURCE_DIR}/patch_install.sh" ${CMAKE_INSTALL_PREFIX}
)
