// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TikTokUploadManager",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "TikTokUploadManager",
            targets: ["TikTokUploadManager"]
        )
    ],
    targets: [
        .executableTarget(
            name: "TikTokUploadManager",
            path: "Sources",
            exclude: [
                "TikTokUploadManager/Services/ai_video_generator.py"
            ]
        )
    ]
)
