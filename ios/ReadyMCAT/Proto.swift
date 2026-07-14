// Copyright: ReadyMCAT contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
//
// A tiny, dependency-free Protocol Buffers reader/writer. The Anki engine
// speaks protobuf bytes over the FFI; for the Wednesday MVP we only need a
// handful of messages, so rather than pull in SwiftProtobuf + a protoc plugin
// we encode/decode those by hand. The wire format is simple:
//   tag = (field_number << 3) | wire_type
//   wire types used here: 0 = varint, 2 = length-delimited (string/bytes/msg)

import Foundation

struct ProtoWriter {
    private(set) var data = Data()

    mutating func varint(_ value: UInt64) {
        var v = value
        repeat {
            var byte = UInt8(v & 0x7F)
            v >>= 7
            if v != 0 { byte |= 0x80 }
            data.append(byte)
        } while v != 0
    }

    mutating func tag(_ field: Int, _ wire: Int) {
        varint(UInt64((field << 3) | wire))
    }

    mutating func int64Field(_ field: Int, _ value: Int64) {
        tag(field, 0)
        varint(UInt64(bitPattern: value))
    }

    mutating func uint64Field(_ field: Int, _ value: UInt64) {
        tag(field, 0)
        varint(value)
    }

    /// proto3 omits false; only write when true.
    mutating func boolField(_ field: Int, _ value: Bool) {
        if value {
            tag(field, 0)
            varint(1)
        }
    }

    mutating func stringField(_ field: Int, _ value: String) {
        let bytes = Data(value.utf8)
        tag(field, 2)
        varint(UInt64(bytes.count))
        data.append(bytes)
    }

    /// Embed raw bytes as a length-delimited field (used for nested messages).
    mutating func bytesField(_ field: Int, _ value: [UInt8]) {
        tag(field, 2)
        varint(UInt64(value.count))
        data.append(contentsOf: value)
    }

    /// Append already-encoded message bytes verbatim (no tag). Used to echo a
    /// server-returned message back with an extra/overridden field appended
    /// (proto3 singular fields are last-wins on decode).
    mutating func raw(_ value: [UInt8]) {
        data.append(contentsOf: value)
    }
}

struct ProtoReader {
    private let data: [UInt8]
    private var idx = 0

    init(_ d: [UInt8]) { data = d }
    init(_ d: Data) { data = [UInt8](d) }

    var hasMore: Bool { idx < data.count }

    mutating func varint() -> UInt64 {
        var result: UInt64 = 0
        var shift: UInt64 = 0
        while idx < data.count {
            let byte = data[idx]
            idx += 1
            result |= UInt64(byte & 0x7F) << shift
            if byte & 0x80 == 0 { break }
            shift += 7
        }
        return result
    }

    /// Returns (fieldNumber, wireType).
    mutating func tag() -> (Int, Int) {
        let t = varint()
        return (Int(t >> 3), Int(t & 7))
    }

    mutating func readBytes(_ count: Int) -> [UInt8] {
        let end = min(idx + count, data.count)
        let slice = Array(data[idx..<end])
        idx = end
        return slice
    }

    mutating func fixed64() -> UInt64 {
        var value: UInt64 = 0
        for shift in stride(from: 0, through: 56, by: 8) {
            if idx < data.count {
                value |= UInt64(data[idx]) << UInt64(shift)
                idx += 1
            }
        }
        return value
    }

    mutating func skip(_ wire: Int) {
        switch wire {
        case 0: _ = varint()
        case 1: idx += 8
        case 2: idx += Int(varint())
        case 5: idx += 4
        default: break
        }
    }
}

enum Proto {
    /// First length-delimited field (bytes of a string or nested message).
    static func firstBytes(_ message: [UInt8], _ field: Int) -> [UInt8]? {
        var r = ProtoReader(message)
        while r.hasMore {
            let (f, w) = r.tag()
            if w == 2 {
                let len = Int(r.varint())
                let bytes = r.readBytes(len)
                if f == field { return bytes }
            } else {
                r.skip(w)
            }
        }
        return nil
    }

    /// Every length-delimited field with the given number (repeated messages).
    static func allBytes(_ message: [UInt8], _ field: Int) -> [[UInt8]] {
        var out: [[UInt8]] = []
        var r = ProtoReader(message)
        while r.hasMore {
            let (f, w) = r.tag()
            if w == 2 {
                let len = Int(r.varint())
                let bytes = r.readBytes(len)
                if f == field { out.append(bytes) }
            } else {
                r.skip(w)
            }
        }
        return out
    }

    /// First varint field with the given number.
    static func firstVarint(_ message: [UInt8], _ field: Int) -> UInt64? {
        var r = ProtoReader(message)
        while r.hasMore {
            let (f, w) = r.tag()
            if w == 0 {
                let v = r.varint()
                if f == field { return v }
            } else {
                r.skip(w)
            }
        }
        return nil
    }

    static func firstString(_ message: [UInt8], _ field: Int) -> String? {
        guard let bytes = firstBytes(message, field) else { return nil }
        return String(decoding: bytes, as: UTF8.self)
    }

    /// Every length-delimited string field with the given number (repeated
    /// `string` — e.g. `Note.fields`, `Note.tags`).
    static func allStrings(_ message: [UInt8], _ field: Int) -> [String] {
        allBytes(message, field).map { String(decoding: $0, as: UTF8.self) }
    }

    /// First `double` field (proto wire type 1, fixed64 little-endian bits).
    static func firstDouble(_ message: [UInt8], _ field: Int) -> Double? {
        var r = ProtoReader(message)
        while r.hasMore {
            let (f, w) = r.tag()
            if w == 1 {
                let bits = r.fixed64()
                if f == field { return Double(bitPattern: bits) }
            } else {
                r.skip(w)
            }
        }
        return nil
    }

    /// A `double` field, defaulting to 0 when absent (proto3 omits zero-valued
    /// scalars, so a missing field genuinely means 0.0).
    static func double(_ message: [UInt8], _ field: Int) -> Double {
        firstDouble(message, field) ?? 0
    }

    /// A `uint32`/`uint64` varint field, defaulting to 0 when absent.
    static func uint(_ message: [UInt8], _ field: Int) -> Int {
        Int(firstVarint(message, field) ?? 0)
    }

    /// A `bool` field, defaulting to false when absent.
    static func bool(_ message: [UInt8], _ field: Int) -> Bool {
        (firstVarint(message, field) ?? 0) != 0
    }

    /// A `string` field, defaulting to "" when absent.
    static func string(_ message: [UInt8], _ field: Int) -> String {
        firstString(message, field) ?? ""
    }
}
