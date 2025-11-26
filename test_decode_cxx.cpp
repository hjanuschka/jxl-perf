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

#include "jxl/decode.h"
#include "jxl/decode_cxx.h"

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

  return 0;
}
