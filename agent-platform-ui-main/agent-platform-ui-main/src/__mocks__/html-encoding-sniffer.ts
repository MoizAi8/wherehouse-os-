export interface EncodingResult {
  encoding: string
  confidence: number
}

export function getEncoding(buffer: Buffer | Uint8Array): EncodingResult {
  if (!buffer || buffer.length === 0) {
    return { encoding: "utf-8", confidence: 1 }
  }

  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer)

  if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    return { encoding: "utf-8", confidence: 1 }
  }

  if (bytes.length >= 2) {
    if (bytes[0] === 0xfe && bytes[1] === 0xff) {
      return { encoding: "utf-16be", confidence: 1 }
    }
    if (bytes[0] === 0xff && bytes[1] === 0xfe) {
      return { encoding: "utf-16le", confidence: 1 }
    }
  }

  let asciiCount = 0
  let nonAsciiCount = 0
  for (let i = 0; i < Math.min(bytes.length, 1024); i++) {
    if (bytes[i] <= 0x7f) {
      asciiCount++
    } else {
      nonAsciiCount++
    }
  }

  if (nonAsciiCount === 0) {
    return { encoding: "ascii", confidence: 1 }
  }

  const utf8Score = validateUtf8(bytes)
  if (utf8Score > 0.95) {
    return { encoding: "utf-8", confidence: utf8Score }
  }

  return { encoding: "windows-1252", confidence: 0.5 }
}

function validateUtf8(bytes: Uint8Array): number {
  let valid = 0
  let total = 0
  let i = 0
  while (i < bytes.length) {
    total++
    const byte = bytes[i]
    if (byte <= 0x7f) {
      valid++
      i++
    } else if ((byte & 0xe0) === 0xc0) {
      if (i + 1 < bytes.length && (bytes[i + 1] & 0xc0) === 0x80) {
        valid++
        i += 2
      } else {
        i++
      }
    } else if ((byte & 0xf0) === 0xe0) {
      if (
        i + 2 < bytes.length &&
        (bytes[i + 1] & 0xc0) === 0x80 &&
        (bytes[i + 2] & 0xc0) === 0x80
      ) {
        valid++
        i += 3
      } else {
        i++
      }
    } else if ((byte & 0xf8) === 0xf0) {
      if (
        i + 3 < bytes.length &&
        (bytes[i + 1] & 0xc0) === 0x80 &&
        (bytes[i + 2] & 0xc0) === 0x80 &&
        (bytes[i + 3] & 0xc0) === 0x80
      ) {
        valid++
        i += 4
      } else {
        i++
      }
    } else {
      i++
    }
  }
  return total > 0 ? valid / total : 1
}

export function sniffEncoding(buffer: Buffer | Uint8Array): string {
  return getEncoding(buffer).encoding
}

export default {
  getEncoding,
  sniffEncoding
}