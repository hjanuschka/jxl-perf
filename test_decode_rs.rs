use jxl::api::{JxlColorType, JxlDataFormat, JxlDecoder, JxlDecoderOptions, JxlOutputBuffer, JxlPixelFormat, ProcessingResult};
use jxl::error::Error;
use std::env;
use std::fs;
use std::time::Instant;

fn main() -> Result<(), Error> {
    let args: Vec<String> = env::args().collect();
    if args.len() != 2 {
        eprintln!("Usage: {} <input.jxl>", args[0]);
        std::process::exit(1);
    }

    let filename = &args[1];

    let start_total = Instant::now();
    let data = fs::read(filename).expect("Failed to read file");
    let read_time = start_total.elapsed();

    let start_parse = Instant::now();
    let mut input = &data[..];
    let decoder = JxlDecoder::new(JxlDecoderOptions::default());
    let mut decoder = loop {
        match decoder.process(&mut input)? {
            ProcessingResult::Complete { result } => break result,
            ProcessingResult::NeedsMoreInput { .. } => {
                return Err(Error::OutOfBounds(0));
            }
        }
    };
    let basic_info = decoder.basic_info().clone();
    let parse_time = start_parse.elapsed();

    let (width, height) = basic_info.size;

    // Determine how to handle extra channels
    // - Alpha channels: blend into RGBA (use None)
    // - Non-alpha channels: need separate F32 buffers (use Some(F32))
    let extra_channel_format: Vec<_> = basic_info
        .extra_channels
        .iter()
        .map(|ec| {
            match ec.ec_type {
                jxl::headers::extra_channels::ExtraChannel::Alpha => None, // Blend into RGBA
                _ => Some(JxlDataFormat::f32()), // Separate F32 buffer for spot colors, CMYK, etc.
            }
        })
        .collect();

    // Count how many separate buffers we need
    let num_separate_channels = extra_channel_format.iter().filter(|ec| ec.is_some()).count();
    let has_alpha = extra_channel_format.iter().any(|ec| ec.is_none());

    let pixel_format = JxlPixelFormat {
        color_type: if has_alpha {
            JxlColorType::Rgba
        } else {
            JxlColorType::Rgb
        },
        color_data_format: Some(JxlDataFormat::U8 { bit_depth: 8 }),
        extra_channel_format,
    };

    decoder.set_pixel_format(pixel_format);

    // Advance to frame info state
    let decoder = loop {
        match decoder.process(&mut input) {
            Ok(ProcessingResult::Complete { result }) => break result,
            Ok(ProcessingResult::NeedsMoreInput { .. }) => {
                return Err(Error::OutOfBounds(0));
            }
            Err(e) => {
                // Some images trigger pipeline setup issues with extra channels
                // Skip them for now (known limitation)
                eprintln!("Error during frame info setup: {:?}", e);
                eprintln!("Skipping image (pipeline setup issue with extra channels)");
                std::process::exit(1);
            }
        }
    };

    // Allocate main color buffer (RGB or RGBA)
    let num_channels = if has_alpha { 4 } else { 3 };
    let bytes_per_row = width * num_channels;
    let mut buffer = vec![0u8; width * height * num_channels];

    // Allocate separate F32 buffers for non-alpha extra channels
    let mut extra_buffers: Vec<Vec<f32>> = (0..num_separate_channels)
        .map(|_| vec![0.0f32; width * height])
        .collect();

    // Create output buffers array
    let mut output_buffers = vec![JxlOutputBuffer::new(&mut buffer, height, bytes_per_row)];

    for extra_buf in &mut extra_buffers {
        let extra_bytes = unsafe {
            std::slice::from_raw_parts_mut(
                extra_buf.as_mut_ptr() as *mut u8,
                extra_buf.len() * std::mem::size_of::<f32>(),
            )
        };
        output_buffers.push(JxlOutputBuffer::new(
            extra_bytes,
            height,
            width * std::mem::size_of::<f32>(),
        ));
    }

    let start_decode = Instant::now();
    let _decoder = loop {
        match decoder.process(&mut input, &mut output_buffers)? {
            ProcessingResult::Complete { result } => break result,
            ProcessingResult::NeedsMoreInput { .. } => {
                return Err(Error::OutOfBounds(0));
            }
        }
    };
    let decode_time = start_decode.elapsed();

    let total_time = start_total.elapsed();

    println!("=== jxl-rs Decode Performance ===");
    println!("File: {}", filename);
    println!("Dimensions: {}x{}", width, height);
    println!("Channels: {}", num_channels);
    println!("---");
    println!("Read time:   {:8.2} ms", read_time.as_secs_f64() * 1000.0);
    println!(
        "Parse time:  {:8.2} ms",
        parse_time.as_secs_f64() * 1000.0
    );
    println!(
        "Decode time: {:8.2} ms",
        decode_time.as_secs_f64() * 1000.0
    );
    println!("Total time:  {:8.2} ms", total_time.as_secs_f64() * 1000.0);
    println!(
        "Throughput:  {:8.2} MP/s",
        (width * height) as f64 / decode_time.as_secs_f64() / 1_000_000.0
    );

    Ok(())
}
