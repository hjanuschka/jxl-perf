// Copyright (c) the JPEG XL Project Authors. All rights reserved.
//
// Use of this source code is governed by a BSD-style
// license that can be found in the LICENSE file.

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <vector>
#include <cstring>
#include <sys/stat.h>

#include "jxl/decode.h"
#include "jxl/decode_cxx.h"
#include <png.h>

int main(int argc, char* argv[]) {
  if (argc != 2) {
    std::cerr << "Usage: " << argv[0] << " <input.jxl>" << std::endl;
    return 1;
  }

  const char* filename = argv[1];

  auto start_total = std::chrono::high_resolution_clock::now();

  std::ifstream file(filename, std::ios::binary | std::ios::ate);
  if (!file) {
    std::cerr << "Failed to open file: " << filename << std::endl;
    return 1;
  }

  std::streamsize size = file.tellg();
  file.seekg(0, std::ios::beg);
  std::vector<uint8_t> data(size);
  if (!file.read(reinterpret_cast<char*>(data.data()), size)) {
    std::cerr << "Failed to read file" << std::endl;
    return 1;
  }

  auto read_time = std::chrono::high_resolution_clock::now() - start_total;

  auto start_parse = std::chrono::high_resolution_clock::now();

  auto dec = JxlDecoderMake(nullptr);
  if (!dec) {
    std::cerr << "JxlDecoderMake failed" << std::endl;
    return 1;
  }

  if (JXL_DEC_SUCCESS !=
      JxlDecoderSubscribeEvents(dec.get(), JXL_DEC_BASIC_INFO |
                                               JXL_DEC_FULL_IMAGE)) {
    std::cerr << "JxlDecoderSubscribeEvents failed" << std::endl;
    return 1;
  }

  JxlDecoderSetInput(dec.get(), data.data(), data.size());
  JxlDecoderCloseInput(dec.get());

  JxlBasicInfo info;
  JxlPixelFormat format = {4, JXL_TYPE_UINT8, JXL_NATIVE_ENDIAN, 0};
  size_t width = 0, height = 0;
  size_t num_channels = 0;

  auto parse_time = std::chrono::nanoseconds(0);
  auto decode_time = std::chrono::nanoseconds(0);

  std::vector<uint8_t> buffer;

  for (;;) {
    JxlDecoderStatus status = JxlDecoderProcessInput(dec.get());

    if (status == JXL_DEC_ERROR) {
      std::cerr << "Decoder error" << std::endl;
      return 1;
    } else if (status == JXL_DEC_NEED_MORE_INPUT) {
      std::cerr << "Error: need more input" << std::endl;
      return 1;
    } else if (status == JXL_DEC_BASIC_INFO) {
      if (JXL_DEC_SUCCESS != JxlDecoderGetBasicInfo(dec.get(), &info)) {
        std::cerr << "JxlDecoderGetBasicInfo failed" << std::endl;
        return 1;
      }
      width = info.xsize;
      height = info.ysize;
      num_channels = (info.num_extra_channels > 0) ? 4 : 3;
      format.num_channels = num_channels;

      parse_time = std::chrono::high_resolution_clock::now() - start_parse;
    } else if (status == JXL_DEC_NEED_IMAGE_OUT_BUFFER) {
      size_t buffer_size;
      if (JXL_DEC_SUCCESS !=
          JxlDecoderImageOutBufferSize(dec.get(), &format, &buffer_size)) {
        std::cerr << "JxlDecoderImageOutBufferSize failed" << std::endl;
        return 1;
      }
      buffer.resize(buffer_size);
      if (JXL_DEC_SUCCESS != JxlDecoderSetImageOutBuffer(dec.get(), &format,
                                                          buffer.data(),
                                                          buffer.size())) {
        std::cerr << "JxlDecoderSetImageOutBuffer failed" << std::endl;
        return 1;
      }
    } else if (status == JXL_DEC_FULL_IMAGE) {
      decode_time = std::chrono::high_resolution_clock::now() - start_parse - parse_time;
      continue;
    } else if (status == JXL_DEC_SUCCESS) {
      break;
    } else {
      std::cerr << "Unknown decoder status" << std::endl;
      return 1;
    }
  }

  auto total_time = std::chrono::high_resolution_clock::now() - start_total;

  std::cout << "=== libjxl Decode Performance ===" << std::endl;
  std::cout << "File: " << filename << std::endl;
  std::cout << "Dimensions: " << width << "x" << height << std::endl;
  std::cout << "Channels: " << num_channels << std::endl;
  std::cout << "---" << std::endl;

  printf("Read time:   %8.2f ms\n",
         std::chrono::duration<double, std::milli>(read_time).count());
  printf("Parse time:  %8.2f ms\n",
         std::chrono::duration<double, std::milli>(parse_time).count());
  printf("Decode time: %8.2f ms\n",
         std::chrono::duration<double, std::milli>(decode_time).count());
  printf("Total time:  %8.2f ms\n",
         std::chrono::duration<double, std::milli>(total_time).count());
  printf("Throughput:  %8.2f MP/s\n",
         (width * height) / std::chrono::duration<double>(decode_time).count() / 1e6);

  // Save PNG for visual verification (AFTER timing!)
  const char* save_png_env = std::getenv("SAVE_PNG");
  if (save_png_env && std::strcmp(save_png_env, "1") == 0) {
    // Extract testname from filename
    std::string filename_str(filename);
    size_t last_slash = filename_str.find_last_of("/\\");
    std::string basename = (last_slash == std::string::npos)
                            ? filename_str
                            : filename_str.substr(last_slash + 1);

    size_t last_dot = basename.find_last_of('.');
    std::string testname = (last_dot == std::string::npos)
                            ? basename
                            : basename.substr(0, last_dot);

    // Create output directory
    mkdir("./out", 0755);

    std::string png_path = "./out/" + testname + ".cxx.png";

    // Save PNG
    FILE* fp = fopen(png_path.c_str(), "wb");
    if (!fp) {
      std::cerr << "Warning: Failed to create PNG file: " << png_path << std::endl;
    } else {
      png_structp png = png_create_write_struct(PNG_LIBPNG_VER_STRING, nullptr, nullptr, nullptr);
      if (!png) {
        std::cerr << "Warning: Failed to create PNG write struct" << std::endl;
        fclose(fp);
      } else {
        png_infop info = png_create_info_struct(png);
        if (!info) {
          std::cerr << "Warning: Failed to create PNG info struct" << std::endl;
          png_destroy_write_struct(&png, nullptr);
          fclose(fp);
        } else {
          if (setjmp(png_jmpbuf(png))) {
            std::cerr << "Warning: Error during PNG creation" << std::endl;
            png_destroy_write_struct(&png, &info);
            fclose(fp);
          } else {
            png_init_io(png, fp);

            // Set image attributes
            png_set_IHDR(
              png,
              info,
              width, height,
              8,
              (num_channels == 4) ? PNG_COLOR_TYPE_RGBA : PNG_COLOR_TYPE_RGB,
              PNG_INTERLACE_NONE,
              PNG_COMPRESSION_TYPE_DEFAULT,
              PNG_FILTER_TYPE_DEFAULT
            );
            png_write_info(png, info);

            // Write image data row by row
            for (size_t y = 0; y < height; y++) {
              png_write_row(png, buffer.data() + y * width * num_channels);
            }

            png_write_end(png, nullptr);
            png_destroy_write_struct(&png, &info);
            fclose(fp);
            std::cout << "Saved PNG: " << png_path << std::endl;
          }
        }
      }
    }
  }

  return 0;
}
