import SwiftUI
import AppKit
import Foundation

@MainActor
final class ClipGeneratorViewModel: ObservableObject {

    enum SourceMode: String, CaseIterable, Identifiable {
        case url = "URL"
        case filePath = "File Path"

        var id: String { rawValue }
    }

    enum ClipFormat: String, CaseIterable, Identifiable {
        case straightHighlight = "straight_highlight"
        case backgroundLayer = "background_layer"
        case commentaryLayer = "commentary_layer"

        var id: String { rawValue }

        var title: String {
            switch self {
            case .straightHighlight:
                return "Straight Highlight"
            case .backgroundLayer:
                return "Background Engagement"
            case .commentaryLayer:
                return "Reaction / Commentary"
            }
        }

        var details: String {
            switch self {
            case .straightHighlight:
                return "Direct highlight cut. Fast and clean."
            case .backgroundLayer:
                return "Adds a dynamic background layer to boost retention."
            case .commentaryLayer:
                return "Adds context-style overlays and a reaction panel look."
            }
        }
    }

    enum ContentTheme: String, CaseIterable, Identifiable {
        case podcast = "podcast"
        case gaming = "gaming"
        case story = "story"
        case motivation = "motivation"
        case drama = "drama"

        var id: String { rawValue }

        var title: String {
            switch self {
            case .podcast:
                return "Podcast / Interview"
            case .gaming:
                return "Gaming"
            case .story:
                return "Story / Education"
            case .motivation:
                return "Motivation / Business"
            case .drama:
                return "Drama / Reaction"
            }
        }
    }

    enum VariationMode: String, CaseIterable, Identifiable {
        case stable = "stable"
        case varied = "varied"
        case wild = "wild"

        var id: String { rawValue }

        var title: String {
            switch self {
            case .stable:
                return "Stable"
            case .varied:
                return "Varied"
            case .wild:
                return "Wild"
            }
        }

        var details: String {
            switch self {
            case .stable:
                return "Predictable clipping pattern."
            case .varied:
                return "Balanced randomness for unique outputs."
            case .wild:
                return "Aggressive variation in cuts and styling."
            }
        }
    }

    enum RunState {
        case idle
        case running
        case succeeded
        case failed
        case stopped
    }

    enum FeedLevel: String, Codable {
        case info
        case success
        case warning
        case error
    }

    struct FeedItem: Identifiable, Codable, Hashable {
        var id: UUID
        var timestamp: Date
        var level: FeedLevel
        var message: String
    }

    struct PostQueueItem: Identifiable, Codable, Hashable {
        enum Status: String, Codable {
            case queued
            case posted
            case removed
        }

        var id: UUID
        var clipFileName: String
        var clipPath: String?
        var caption: String
        var createdAt: Date
        var scheduledAt: Date?
        var status: Status
    }

    struct PostHistoryItem: Identifiable, Codable, Hashable {
        enum Outcome: String, Codable {
            case posted
            case removed
        }

        var id: UUID
        var clipFileName: String
        var clipPath: String?
        var caption: String
        var completedAt: Date
        var outcome: Outcome
        var notes: String
    }

    @Published var sourceMode: SourceMode = .url
    @Published var videoURL: String = ""
    @Published var clipDuration: Int = 30
    @Published var maxClips: Int = 2
    @Published var addCaptions: Bool = true
    @Published var addMusic: Bool = true
    @Published var applyEffects: Bool = true
    @Published var clipFormat: ClipFormat = .backgroundLayer
    @Published var contentTheme: ContentTheme = .story
    @Published var variationMode: VariationMode = .varied

    // Enhanced features
    @Published var useSmartBackgrounds: Bool = false
    @Published var backgroundTheme: String = "scary"
    @Published var selectedAccountUsername: String = ""
    @Published var autoTrackPost: Bool = false

    @Published var isProcessing = false
    @Published var progressText = "Idle"
    @Published var progressValue: Double? = nil
    @Published var logs: String = ""
    @Published var generatedClips: [Clip] = []
    @Published var runState: RunState = .idle

    @Published var postCaptionDraft: String = ""
    @Published var postHashtags: String = "#fyp #viral #clips"
    @Published var schedulePost: Bool = false
    @Published var scheduledPostDate: Date = Date().addingTimeInterval(60 * 60)
    @Published var postQueue: [PostQueueItem] = []
    @Published var postHistory: [PostHistoryItem] = []
    @Published var updatesFeed: [FeedItem] = []
    @Published var postStatusText: String = "No post action yet."
    @Published var lastRunSummary: String = "No generation runs yet."
    @Published var lastRunAt: Date?

    private let service = PythonProcessService()
    private var outputBuffer = ""
    private var didRequestStop = false
    private var sawErrorOutput = false
    private var processExitCode: Int32?
    private let queueStorageURL: URL
    private let historyStorageURL: URL
    private let clipsStorageURL: URL

    init() {
        let appSupportURL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSTemporaryDirectory())
        let appDirectory = appSupportURL.appendingPathComponent("TikTokUploadManager", isDirectory: true)
        queueStorageURL = appDirectory.appendingPathComponent("post_queue.json")
        historyStorageURL = appDirectory.appendingPathComponent("post_history.json")
        clipsStorageURL = appDirectory.appendingPathComponent("generated_clips.json")

        // Ensure storage directory exists on init
        do {
            try FileManager.default.createDirectory(at: appDirectory, withIntermediateDirectories: true)
            print("✅ Storage directory ready: \(appDirectory.path)")
        } catch {
            print("⚠️ Failed to create storage directory: \(error.localizedDescription)")
        }

        loadGeneratedClips()
        loadPostState()
        appendFeed("New UI ready. Clip Creator, Generated Clips, and Post are active.", level: .info)
    }

    func pickVideoFile() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [
            .mpeg4Movie,
            .quickTimeMovie,
            .avi,
            .movie,
            .mpeg2Video,
            .video
        ]

        if panel.runModal() == .OK, let url = panel.url {
            sourceMode = .filePath
            videoURL = url.path
        }
    }

    func generateClips() {
        guard !videoURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            progressText = "Provide a video URL or local file path."
            runState = .failed
            progressValue = nil
            appendFeed("Generation blocked: missing source URL or file path.", level: .warning)
            return
        }

        isProcessing = true
        runState = .running
        progressText = "Starting..."
        progressValue = 0
        logs = ""
        outputBuffer = ""
        didRequestStop = false
        sawErrorOutput = false
        processExitCode = nil

        let runSummary = "format=\(clipFormat.rawValue), theme=\(contentTheme.rawValue), variation=\(variationMode.rawValue)"
        appendFeed("Generation started (\(runSummary)).", level: .info)

        var args = [
            "--url", videoURL,
            "--duration", "\(clipDuration)",
            "--max_clips", "\(maxClips)",
            "--captions", "\(addCaptions)",
            "--music", "\(addMusic)",
            "--effects", "\(applyEffects)",
            "--clip_format", clipFormat.rawValue,
            "--content_theme", contentTheme.rawValue,
            "--variation_mode", variationMode.rawValue
        ]

        if variationMode != .stable {
            args += ["--run_seed", UUID().uuidString]
        }

        // Enhanced features
        if useSmartBackgrounds {
            args += ["--use_smart_backgrounds", "true", "--background_theme", backgroundTheme]
        }

        if autoTrackPost && !selectedAccountUsername.isEmpty {
            args += ["--auto_track", "true", "--account_username", selectedAccountUsername]
        }

        service.runScript(arguments: args) { [weak self] output in
            self?.consumeOutput(output)
        } completion: { [weak self] in
            guard let self else { return }
            self.isProcessing = false

            if self.didRequestStop {
                self.runState = .stopped
                self.progressText = "Stopped"
                self.progressValue = nil
                self.appendFeed("Generation stopped by user.", level: .warning)
                return
            }

            if let exitCode = self.processExitCode, exitCode != 0 {
                self.runState = .failed
                if self.progressText == "Starting..." {
                    self.progressText = "Failed (exit code \(exitCode))"
                }
                self.appendFeed("Generation failed with exit code \(exitCode).", level: .error)
                return
            }

            if self.sawErrorOutput {
                self.runState = .failed
                if self.progressText == "Starting..." {
                    self.progressText = "Failed"
                }
                self.appendFeed("Generation failed. Check logs in Run Output.", level: .error)
                return
            }

            self.runState = .succeeded
            self.progressValue = 1
            self.lastRunAt = Date()
            self.lastRunSummary = "Generated \(self.generatedClips.count) clip(s) using \(self.clipFormat.title) • \(self.contentTheme.title) • \(self.variationMode.title)."
            if self.progressText == "Starting..." {
                self.progressText = "Finished"
            }
            self.appendFeed(self.lastRunSummary, level: .success)
        }
    }

    func stop() {
        didRequestStop = true
        service.stop()
        isProcessing = false
        runState = .stopped
        progressText = "Stopped"
        progressValue = nil
        appendFeed("Background process terminated.", level: .warning)
    }

    func applySuggestedCaption(for clip: Clip?) {
        let trimmedTags = postHashtags.trimmingCharacters(in: .whitespacesAndNewlines)

        guard let clip else {
            postCaptionDraft = ""
            return
        }

        let hook = captionHook(for: contentTheme)
        var lines: [String] = [
            "\(hook)",
            "\(clipFormat.title) cut from a longer video.",
            ""
        ]

        if !trimmedTags.isEmpty {
            lines.append(trimmedTags)
        }

        postCaptionDraft = lines.joined(separator: "\n")
        postStatusText = "Suggested caption loaded for \(clip.fileName)."
    }

    func queueClipForPost(_ clip: Clip?) {
        guard let clip else {
            postStatusText = "Select a generated clip first."
            appendFeed("Post queue add failed: no selected clip.", level: .warning)
            return
        }

        var caption = postCaptionDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        if caption.isEmpty {
            applySuggestedCaption(for: clip)
            caption = postCaptionDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        }

        let item = PostQueueItem(
            id: UUID(),
            clipFileName: clip.fileName,
            clipPath: clip.path,
            caption: caption,
            createdAt: Date(),
            scheduledAt: schedulePost ? scheduledPostDate : nil,
            status: .queued
        )

        postQueue.insert(item, at: 0)
        savePostState()

        postStatusText = "Queued \(clip.fileName) for posting."
        appendFeed("Queued \(clip.fileName) for Post tab workflow.", level: .success)
    }

    func removeQueueItem(_ item: PostQueueItem) {
        guard let index = postQueue.firstIndex(where: { $0.id == item.id }) else { return }
        let removed = postQueue.remove(at: index)

        let history = PostHistoryItem(
            id: UUID(),
            clipFileName: removed.clipFileName,
            clipPath: removed.clipPath,
            caption: removed.caption,
            completedAt: Date(),
            outcome: .removed,
            notes: "Removed from queue"
        )
        postHistory.insert(history, at: 0)
        savePostState()

        postStatusText = "Removed \(removed.clipFileName) from queue."
        appendFeed("Removed \(removed.clipFileName) from queue.", level: .warning)
    }

    func markQueueItemPosted(_ item: PostQueueItem) {
        guard let index = postQueue.firstIndex(where: { $0.id == item.id }) else { return }
        let postedItem = postQueue.remove(at: index)

        let history = PostHistoryItem(
            id: UUID(),
            clipFileName: postedItem.clipFileName,
            clipPath: postedItem.clipPath,
            caption: postedItem.caption,
            completedAt: Date(),
            outcome: .posted,
            notes: postedItem.scheduledAt == nil ? "Posted manually" : "Posted from scheduled queue"
        )
        postHistory.insert(history, at: 0)
        savePostState()

        postStatusText = "Marked \(postedItem.clipFileName) as posted."
        appendFeed("Posted \(postedItem.clipFileName).", level: .success)
    }

    func copyCaptionToClipboard() {
        let payload = postCaptionDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !payload.isEmpty else {
            postStatusText = "Caption is empty."
            appendFeed("Copy caption skipped: draft is empty.", level: .warning)
            return
        }

        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(payload, forType: .string)
        postStatusText = "Caption copied to clipboard."
        appendFeed("Caption copied to clipboard.", level: .info)
    }

    func openTikTokUploadPage(videoPath: String? = nil, caption: String? = nil) {
        print("🚀 [TikTok Upload] Starting upload process...")
        print("   Video: \(videoPath ?? "none")")
        print("   Caption: \(caption ?? "none")")

        // Validate video path
        guard let videoPath = videoPath, !videoPath.isEmpty else {
            postStatusText = "No video selected for upload."
            appendFeed("Upload failed: No video selected", level: .error)
            print("❌ [TikTok Upload] No video path provided")
            return
        }

        guard FileManager.default.fileExists(atPath: videoPath) else {
            postStatusText = "Video file not found: \(videoPath)"
            appendFeed("Upload failed: Video file not found", level: .error)
            print("❌ [TikTok Upload] Video file not found at: \(videoPath)")
            return
        }

        // Auto-fill TikTok upload using Python script with tiktok-uploader
        // Try to find the script in multiple locations
        var pythonPath: String? = nil

        // First, try the development location
        let devPath = NSHomeDirectory() + "/TikTokUploadManager/Python/tiktok_upload_cli.py"
        if FileManager.default.fileExists(atPath: devPath) {
            pythonPath = devPath
            print("✅ [TikTok Upload] Found script at: \(devPath)")
        } else {
            // Fall back to bundle
            pythonPath = Bundle.main.path(forResource: "tiktok_upload_cli", ofType: "py")
            if let path = pythonPath {
                print("✅ [TikTok Upload] Found script in bundle: \(path)")
            }
        }

        guard let scriptPath = pythonPath else {
            postStatusText = "Upload script not found."
            appendFeed("Failed to find tiktok_upload_cli.py", level: .error)
            print("❌ [TikTok Upload] Script not found")
            return
        }

        var args = [scriptPath, "--video", videoPath]

        // Use provided caption or generate one
        var finalCaption = caption ?? ""
        if finalCaption.isEmpty {
            print("ℹ️ [TikTok Upload] No caption provided, generating default caption")
            let hook = captionHook(for: contentTheme)
            let tags = postHashtags.trimmingCharacters(in: .whitespacesAndNewlines)
            finalCaption = "\(hook)\n\(clipFormat.title) cut from a longer video.\n\n\(tags)"
        }

        args += ["--caption", finalCaption]

        print("📝 [TikTok Upload] Using caption: \(finalCaption.prefix(100))...")

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = args

        // Capture output
        let outputPipe = Pipe()
        let errorPipe = Pipe()
        process.standardOutput = outputPipe
        process.standardError = errorPipe

        do {
            try process.run()

            postStatusText = "Opening TikTok upload page with auto-fill..."
            appendFeed("Starting TikTok upload auto-fill...", level: .info)

            // Read output in background
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                process.waitUntilExit()

                let outputData = outputPipe.fileHandleForReading.readDataToEndOfFile()
                let errorData = errorPipe.fileHandleForReading.readDataToEndOfFile()

                let output = String(data: outputData, encoding: .utf8) ?? ""
                let errorOutput = String(data: errorData, encoding: .utf8) ?? ""

                print("📊 [TikTok Upload] Process completed with status: \(process.terminationStatus)")
                if !output.isEmpty {
                    print("   Output: \(output)")
                }
                if !errorOutput.isEmpty {
                    print("   Error: \(errorOutput)")
                }

                DispatchQueue.main.async {
                    if process.terminationStatus == 0 {
                        self?.postStatusText = "TikTok upload page opened and auto-filled successfully."
                        self?.appendFeed("TikTok upload auto-fill completed.", level: .success)
                    } else {
                        let message = !errorOutput.isEmpty ? errorOutput : (!output.isEmpty ? output : "Upload process failed")
                        self?.postStatusText = "Upload auto-fill failed"
                        self?.appendFeed("Upload failed: \(message)", level: .error)
                    }
                }
            }
        } catch {
            postStatusText = "Failed to run upload script: \(error.localizedDescription)"
            appendFeed("Failed to run upload script: \(error.localizedDescription)", level: .error)
            print("❌ [TikTok Upload] Failed to start process: \(error.localizedDescription)")
        }
    }

    func openClip(_ clip: Clip?) {
        guard let path = clip?.path, !path.isEmpty else {
            postStatusText = "Selected clip has no local file path."
            return
        }

        NSWorkspace.shared.open(URL(fileURLWithPath: path))
        postStatusText = "Opened \(clip?.fileName ?? "clip") in default player."
    }

    func revealClipInFinder(_ clip: Clip?) {
        guard let path = clip?.path, !path.isEmpty else {
            postStatusText = "Selected clip has no local file path."
            return
        }

        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
        postStatusText = "Revealed \(clip?.fileName ?? "clip") in Finder."
    }

    func openQueueItemClip(_ item: PostQueueItem) {
        guard let path = item.clipPath, !path.isEmpty else {
            postStatusText = "Queued item has no local clip path."
            return
        }

        NSWorkspace.shared.open(URL(fileURLWithPath: path))
        postStatusText = "Opened \(item.clipFileName)."
    }

    private func consumeOutput(_ output: String) {
        logs += output
        outputBuffer += output

        var lines = outputBuffer.components(separatedBy: .newlines)
        outputBuffer = lines.popLast() ?? ""

        for line in lines {
            handleOutputLine(line)
        }
    }

    private func handleOutputLine(_ line: String) {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        if trimmed.hasPrefix("CLIP_JSON:") {
            parseClipJSON(trimmed)
            return
        }

        if trimmed.hasPrefix("CLIP_GENERATED:") {
            let payload = trimmed.replacingOccurrences(of: "CLIP_GENERATED:", with: "")
                .trimmingCharacters(in: .whitespaces)
            let clip = Clip(fileName: payload.isEmpty ? "Clip \(generatedClips.count + 1)" : payload,
                            duration: clipDuration,
                            size: "—")
            upsertClip(clip)
            progressText = "Generated \(clip.fileName)"
            return
        }

        if let exitCode = parseExitCode(from: trimmed) {
            processExitCode = exitCode

            if exitCode == 0 {
                if !didRequestStop && !sawErrorOutput {
                    runState = .succeeded
                }
            } else if !didRequestStop {
                sawErrorOutput = true
                runState = .failed
                progressText = "Process exited with code \(exitCode)."
            }
            return
        }

        if trimmed.hasPrefix("ERROR:") {
            sawErrorOutput = true
            runState = .failed
            progressText = trimmed
            appendFeed(trimmed, level: .error)
            return
        }

        progressText = trimmed

        if let (step, total) = parseStep(from: trimmed), total > 0 {
            progressValue = min(max(Double(step) / Double(total), 0), 1)
        }

        if trimmed.hasPrefix("DONE:") {
            runState = .succeeded
            progressValue = 1
        }
    }

    private func parseStep(from line: String) -> (Int, Int)? {
        // Matches strings like "Step 2/5: Creating clips..."
        guard let range = line.range(of: #"Step\s+(\d+)\s*/\s*(\d+)"#, options: .regularExpression) else {
            return nil
        }

        let match = String(line[range])
        let numbers = match.components(separatedBy: CharacterSet.decimalDigits.inverted).compactMap { Int($0) }
        guard numbers.count >= 2 else { return nil }
        return (numbers[0], numbers[1])
    }

    private func parseClipJSON(_ line: String) {
        let jsonString = line.replacingOccurrences(of: "CLIP_JSON:", with: "")
            .trimmingCharacters(in: .whitespaces)

        guard let data = jsonString.data(using: .utf8) else { return }
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }

        let fileName = object["fileName"] as? String ?? "Clip \(generatedClips.count + 1)"
        let duration = object["duration"] as? Int ?? clipDuration
        let size = object["size"] as? String ?? "—"
        let path = object["path"] as? String

        upsertClip(Clip(fileName: fileName, duration: duration, size: size, path: path))
    }

    private func parseExitCode(from line: String) -> Int32? {
        let prefix = "Process exited with code "
        guard line.hasPrefix(prefix) else { return nil }

        let suffix = line.dropFirst(prefix.count)
        let code = suffix.prefix { $0 == "-" || $0.isNumber }
        guard !code.isEmpty else { return nil }

        return Int32(code)
    }

    private func upsertClip(_ clip: Clip) {
        if let index = generatedClips.firstIndex(where: { $0.fileName == clip.fileName }) {
            generatedClips[index] = clip
        } else {
            generatedClips.append(clip)
        }

        saveGeneratedClips()

        if generatedClips.count == 1 {
            applySuggestedCaption(for: clip)
        }
    }

    private func captionHook(for theme: ContentTheme) -> String {
        switch theme {
        case .podcast:
            return "This podcast moment hits hard."
        case .gaming:
            return "Wait for the clutch play at the end."
        case .story:
            return "Quick breakdown you can use right now."
        case .motivation:
            return "Save this mindset shift for later."
        case .drama:
            return "This reaction changed everything."
        }
    }

    private func appendFeed(_ message: String, level: FeedLevel) {
        let item = FeedItem(id: UUID(), timestamp: Date(), level: level, message: message)
        updatesFeed.insert(item, at: 0)
        if updatesFeed.count > 120 {
            updatesFeed.removeLast(updatesFeed.count - 120)
        }
    }

    private func loadPostState() {
        do {
            try ensureStorageDirectoryExists()
        } catch {
            appendFeed("Failed to create app support directory: \(error.localizedDescription)", level: .warning)
            return
        }

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        if let queueData = try? Data(contentsOf: queueStorageURL),
           let decodedQueue = try? decoder.decode([PostQueueItem].self, from: queueData) {
            postQueue = decodedQueue
        }

        if let historyData = try? Data(contentsOf: historyStorageURL),
           let decodedHistory = try? decoder.decode([PostHistoryItem].self, from: historyData) {
            postHistory = decodedHistory
        }
    }

    private func savePostState() {
        do {
            try ensureStorageDirectoryExists()

            let encoder = JSONEncoder()
            encoder.dateEncodingStrategy = .iso8601
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]

            let queueData = try encoder.encode(postQueue)
            let historyData = try encoder.encode(postHistory)

            try queueData.write(to: queueStorageURL, options: .atomic)
            try historyData.write(to: historyStorageURL, options: .atomic)
        } catch {
            appendFeed("Failed to save post state: \(error.localizedDescription)", level: .warning)
        }
    }

    private func loadGeneratedClips() {
        do {
            try ensureStorageDirectoryExists()
        } catch {
            print("⚠️ Failed to create app support directory: \(error.localizedDescription)")
            appendFeed("Failed to create app support directory: \(error.localizedDescription)", level: .warning)
            return
        }

        let decoder = JSONDecoder()

        guard FileManager.default.fileExists(atPath: clipsStorageURL.path) else {
            print("ℹ️ No saved clips file found at \(clipsStorageURL.path)")
            return
        }

        guard let data = try? Data(contentsOf: clipsStorageURL),
              let decodedClips = try? decoder.decode([Clip].self, from: data) else {
            print("⚠️ Failed to decode clips from \(clipsStorageURL.path)")
            return
        }

        generatedClips = decodedClips
        print("✅ Loaded \(generatedClips.count) clips from storage")

        // Verify paths still exist and update status
        let validClips = generatedClips.filter { clip in
            guard let path = clip.path else { return false }
            return FileManager.default.fileExists(atPath: path)
        }

        if validClips.count < generatedClips.count {
            print("⚠️ \(generatedClips.count - validClips.count) clips have missing video files")
            appendFeed("Some saved clips have missing video files", level: .warning)
        }
    }

    private func saveGeneratedClips() {
        do {
            try ensureStorageDirectoryExists()

            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let clipsData = try encoder.encode(generatedClips)
            try clipsData.write(to: clipsStorageURL, options: .atomic)

            print("✅ Saved \(generatedClips.count) clips to \(clipsStorageURL.path)")
        } catch {
            print("❌ Failed to save generated clips: \(error.localizedDescription)")
            print("   Target path: \(clipsStorageURL.path)")
            appendFeed("Failed to save generated clips: \(error.localizedDescription)", level: .warning)
        }
    }

    private func ensureStorageDirectoryExists() throws {
        try FileManager.default.createDirectory(
            at: queueStorageURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
    }
}
