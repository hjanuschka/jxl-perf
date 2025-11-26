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
    let num_extra_channels = basic_info.extra_channels.len();

    // Skip images with non-alpha extra channels for benchmark simplicity
    // These include CMYK, spot colors, etc. that need complex handling
    let has_non_alpha_channels = basic_info
        .extra_channels
        .iter()
        .any(|ec| !matches!(ec.ec_type, jxl::headers::extra_channels::ExtraChannel::Alpha));

    if has_non_alpha_channels {
        eprintln!("Skipping image with non-alpha extra channels (CMYK, spot colors, etc.)");
        std::process::exit(1);
    }

    // For alpha channels, use None to blend into RGBA
    let extra_channel_format = vec![None; num_extra_channels];

    let pixel_format = JxlPixelFormat {
        color_type: if num_extra_channels > 0 {
            JxlColorType::Rgba
        } else {
            JxlColorType::Rgb
        },
        color_data_format: Some(JxlDataFormat::U8 { bit_depth: 8 }),
        extra_channel_format,
    };

    decoder.set_pixel_format(pixel_format);
    let decoder = loop {
        match decoder.process(&mut input)? {
            ProcessingResult::Complete { result } => break result,
            ProcessingResult::NeedsMoreInput { .. } => {
                return Err(Error::OutOfBounds(0));
            }
        }
    };

    let num_channels = if num_extra_channels > 0 { 4 } else { 3 };
    let bytes_per_row = width * num_channels;
    let mut buffer = vec![0u8; width * height * num_channels];

    let mut output_buffer = JxlOutputBuffer::new(&mut buffer, height, bytes_per_row);

    let start_decode = Instant::now();
    let _decoder = loop {
        match decoder.process(&mut input, &mut [output_buffer])? {
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
