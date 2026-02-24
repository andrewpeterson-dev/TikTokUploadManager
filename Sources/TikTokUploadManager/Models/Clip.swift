import Foundation

struct Clip: Identifiable, Codable, Hashable {
    let id: UUID
    let fileName: String
    let duration: Int
    let size: String
    let path: String?

    init(id: UUID = UUID(), fileName: String, duration: Int, size: String, path: String? = nil) {
        self.id = id
        self.fileName = fileName
        self.duration = duration
        self.size = size
        self.path = path
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case fileName
        case duration
        case size
        case path
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decodeIfPresent(UUID.self, forKey: .id) ?? UUID()
        fileName = try container.decode(String.self, forKey: .fileName)
        duration = try container.decode(Int.self, forKey: .duration)
        size = try container.decode(String.self, forKey: .size)
        path = try container.decodeIfPresent(String.self, forKey: .path)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(fileName, forKey: .fileName)
        try container.encode(duration, forKey: .duration)
        try container.encode(size, forKey: .size)
        try container.encodeIfPresent(path, forKey: .path)
    }
}
