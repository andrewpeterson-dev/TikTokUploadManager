import Foundation

struct Clip: Identifiable, Codable, Hashable {
    let id: UUID
    let videoId: Int?
    let fileName: String
    let duration: Int
    let size: String
    let path: String?
    let status: String
    let uploadStatus: String?
    let retryCount: Int?

    init(
        id: UUID = UUID(),
        videoId: Int? = nil,
        fileName: String,
        duration: Int,
        size: String,
        path: String? = nil,
        status: String = "draft",
        uploadStatus: String? = nil,
        retryCount: Int? = nil
    ) {
        self.id = id
        self.videoId = videoId
        self.fileName = fileName
        self.duration = duration
        self.size = size
        self.path = path
        self.status = status
        self.uploadStatus = uploadStatus
        self.retryCount = retryCount
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case videoId
        case fileName
        case duration
        case size
        case path
        case status
        case uploadStatus
        case retryCount
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decodeIfPresent(UUID.self, forKey: .id) ?? UUID()
        videoId = try container.decodeIfPresent(Int.self, forKey: .videoId)
        fileName = try container.decode(String.self, forKey: .fileName)
        duration = try container.decode(Int.self, forKey: .duration)
        size = try container.decode(String.self, forKey: .size)
        path = try container.decodeIfPresent(String.self, forKey: .path)
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? "draft"
        uploadStatus = try container.decodeIfPresent(String.self, forKey: .uploadStatus)
        retryCount = try container.decodeIfPresent(Int.self, forKey: .retryCount)
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encodeIfPresent(videoId, forKey: .videoId)
        try container.encode(fileName, forKey: .fileName)
        try container.encode(duration, forKey: .duration)
        try container.encode(size, forKey: .size)
        try container.encodeIfPresent(path, forKey: .path)
        try container.encode(status, forKey: .status)
        try container.encodeIfPresent(uploadStatus, forKey: .uploadStatus)
        try container.encodeIfPresent(retryCount, forKey: .retryCount)
    }
}
