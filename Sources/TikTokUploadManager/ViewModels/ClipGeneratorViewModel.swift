import SwiftUI
import AppKit
import Foundation
import AVFoundation

@MainActor
final class ClipGeneratorViewModel: ObservableObject {

    enum SourceMode: String, CaseIterable, Identifiable {
        case url = "URL"
        case filePath = "File Path"
        case aiVideo = "AI Video"

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

    enum AIVideoTheme: String, CaseIterable, Identifiable {
        case scary = "scary"
        case dating = "dating"
        case crazy = "crazy"
        case mystery = "mystery"
        case motivational = "motivational"
        case creepy = "creepy"
        case interesting = "interesting"

        var id: String { rawValue }

        var title: String {
            switch self {
            case .scary:
                return "👻 Horror"
            case .dating:
                return "💕 Romance"
            case .crazy:
                return "🤯 Wild"
            case .mystery:
                return "🔍 Mystery"
            case .motivational:
                return "💪 Inspire"
            case .creepy:
                return "😱 Creepy"
            case .interesting:
                return "🌟 Facts"
            }
        }
    }

    enum AIVideoDuration: Int, CaseIterable, Identifiable {
        case thirty = 30
        case sixty = 60
        case ninety = 90
        case onetwenty = 120

        var id: Int { rawValue }

        var title: String {
            switch self {
            case .thirty:
                return "⚡ 30s Quick"
            case .sixty:
                return "📱 60s Standard"
            case .ninety:
                return "📹 90s Extended"
            case .onetwenty:
                return "🎬 120s Long"
            }
        }
    }

    enum AIVideoType: String, CaseIterable, Identifiable {
        case story = "story"
        case commentary = "commentary"
        case news = "news"

        var id: String { rawValue }

        var title: String {
            switch self {
            case .story:
                return "📖 Story"
            case .commentary:
                return "🎙️ Commentary"
            case .news:
                return "📰 News"
            }
        }

        var description: String {
            switch self {
            case .story:
                return "AI-generated narrative stories"
            case .commentary:
                return "Commentary style videos with analysis"
            case .news:
                return "News-style reporting videos"
            }
        }
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

    @Published var useSmartBackgrounds: Bool = false
    @Published var backgroundTheme: String = "scary"
    @Published var selectedAccountUsername: String = ""
    @Published var autoTrackPost: Bool = false
    @Published var shortformAIEnabled: Bool = true
    @Published var shortformAestheticThreshold: Int = 75
    @Published var shortformEngagementThreshold: Int = 70
    @Published var shortformDetectedThisRun: Bool = false
    @Published var shortformLastAestheticScore: Int?
    @Published var shortformLastEngagementScore: Int?
    @Published var shortformLastValidationSource: String = "n/a"
    @Published var shortformLastCorrections: String = "none"
    @Published var shortformLastError: String = ""

    // AI Video Generation settings
    @Published var aiVideoTheme: AIVideoTheme = .scary
    @Published var aiVideoDuration: AIVideoDuration = .sixty
    @Published var aiVideoType: AIVideoType = .story

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

    private let generationService = PythonProcessService()
    private let featuresService = TikTokFeaturesService()

    private var outputBuffer = ""
    private var didRequestStop = false
    private var sawErrorOutput = false
    private var aiOutputPendingBuffer = ""
    private var aiVideoGeneratedSeen = false
    private var aiVideoPayloadSeen = false
    private var aiVideoDoneSeen = false
    private var processExitCode: Int32?

    private let queueStorageURL: URL
    private let historyStorageURL: URL
    private var uploadWorkerProcess: Process?

    init() {
        let appSupportURL = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSTemporaryDirectory())
        let appDirectory = appSupportURL.appendingPathComponent("TikTokUploadManager", isDirectory: true)

        queueStorageURL = appDirectory.appendingPathComponent("post_queue.json")
        historyStorageURL = appDirectory.appendingPathComponent("post_history.json")

        do {
            try FileManager.default.createDirectory(at: appDirectory, withIntermediateDirectories: true)
        } catch {
            appendFeed("Failed to create app support directory: \(error.localizedDescription)", level: .warning)
        }

        loadPostState()
        refreshGeneratedClipsFromBackend()
        startUploadWorker()

        appendFeed("Production backend connected. Video metadata now loads from SQLite.", level: .info)
    }

    deinit {
        uploadWorkerProcess?.terminate()
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
        // Handle AI Video generation separately
        if sourceMode == .aiVideo {
            generateAIVideo()
            return
        }

        guard !videoURL.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            progressText = "Provide a video URL or local file path."
            runState = .failed
            progressValue = nil
            appendFeed("Generation blocked: missing source URL or file path.", level: .warning)
            return
        }

        // Validate local file path exists before processing
        let trimmedURL = videoURL.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedURL.starts(with: "http://") && !trimmedURL.starts(with: "https://") {
            // This appears to be a local file path
            let filePath = NSString(string: trimmedURL).expandingTildeInPath
            if !FileManager.default.fileExists(atPath: filePath) {
                progressText = "Video file not found"
                runState = .failed
                progressValue = nil
                appendFeed("ERROR: Video file not found at path: \(filePath)", level: .error)
                appendFeed("TIP: Use the Browse button to select your video file instead of typing the path.", level: .warning)
                return
            }
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
        shortformDetectedThisRun = false
        shortformLastAestheticScore = nil
        shortformLastEngagementScore = nil
        shortformLastValidationSource = "n/a"
        shortformLastCorrections = "none"
        shortformLastError = ""

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

        if useSmartBackgrounds {
            args += ["--use_smart_backgrounds", "true", "--background_theme", backgroundTheme]
        }

        if autoTrackPost && !selectedAccountUsername.isEmpty {
            args += ["--auto_track", "true", "--account_username", selectedAccountUsername]
        }
        args += [
            "--shortform_ai", "\(shortformAIEnabled)",
            "--aesthetic_threshold", "\(shortformAestheticThreshold)",
            "--engagement_threshold", "\(shortformEngagementThreshold)"
        ]

        generationService.runScript(arguments: args) { [weak self] output in
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
            self.lastRunSummary = "Generated clips using \(self.clipFormat.title) • \(self.contentTheme.title) • \(self.variationMode.title)."
            if self.progressText == "Starting..." {
                self.progressText = "Finished"
            }
            self.appendFeed(self.lastRunSummary, level: .success)
            self.refreshGeneratedClipsFromBackend()
        }
    }

    func stop() {
        didRequestStop = true
        generationService.stop()
        isProcessing = false
        runState = .stopped
        progressText = "Stopped"
        progressValue = nil
        appendFeed("Background process terminated.", level: .warning)
    }

    func generateAIVideo() {
        isProcessing = true
        runState = .running
        progressText = "Generating AI video..."
        progressValue = 0
        logs = ""
        outputBuffer = ""
        didRequestStop = false
        sawErrorOutput = false
        aiOutputPendingBuffer = ""
        aiVideoGeneratedSeen = false
        aiVideoPayloadSeen = false
        aiVideoDoneSeen = false
        processExitCode = nil

        let runSummary = "AI video: theme=\(aiVideoTheme.rawValue), duration=\(aiVideoDuration.rawValue)s, type=\(aiVideoType.rawValue)"
        appendFeed("AI video generation started (\(runSummary)).", level: .info)

        // Run the backend command
        let args = [
            "generate-ai-video",
            "--theme", aiVideoTheme.rawValue,
            "--duration", "\(aiVideoDuration.rawValue)",
            "--video-type", aiVideoType.rawValue
        ]

        // Use bash to run python command from project root (not app subdirectory)
        let backendPath = NSHomeDirectory() + "/TikTokUploadManager"
        let command = "cd '\(backendPath)' && python3 -m app.main \(args.joined(separator: " "))"

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/bin/bash")
            process.arguments = ["-c", command]

            // Set up environment: unbuffered Python output and proper PATH for Homebrew python3
            var env = ProcessInfo.processInfo.environment
            env["PYTHONUNBUFFERED"] = "1"
            let existingPath = env["PATH"] ?? "/usr/bin:/bin"
            env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:\(NSHomeDirectory())/bin:\(existingPath)"
            process.environment = env

            // Use separate pipes for stdout and stderr to prevent moviepy/tqdm
            // stderr writes from causing BrokenPipeError on the structured stdout pipe.
            let stdoutPipe = Pipe()
            let stderrPipe = Pipe()
            process.standardOutput = stdoutPipe
            process.standardError = stderrPipe

            let handle = stdoutPipe.fileHandleForReading
            handle.readabilityHandler = { fileHandle in
                let data = fileHandle.availableData
                if !data.isEmpty, let line = String(data: data, encoding: .utf8) {
                    Task { @MainActor in
                        self?.handleAIVideoOutputChunk(line)
                    }
                }
            }

            // Drain stderr separately — log it but don't treat as structured output.
            let stderrHandle = stderrPipe.fileHandleForReading
            stderrHandle.readabilityHandler = { fileHandle in
                let data = fileHandle.availableData
                if !data.isEmpty, let text = String(data: data, encoding: .utf8) {
                    Task { @MainActor in
                        self?.appendAIVideoLogs("[stderr] " + text)
                    }
                }
            }

            do {
                try process.run()
                process.waitUntilExit()

                Task { @MainActor in
                    let remainingData = handle.readDataToEndOfFile()
                    let trailingOutput = String(data: remainingData, encoding: .utf8)

                    handle.readabilityHandler = nil
                    stderrHandle.readabilityHandler = nil

                    if let trailingOutput, !trailingOutput.isEmpty {
                        self?.handleAIVideoOutputChunk(trailingOutput)
                    }
                    self?.handleAIVideoExit(process.terminationStatus)
                }
            } catch {
                Task { @MainActor in
                    self?.appendFeed("Failed to start AI video generation: \(error)", level: .error)
                    self?.isProcessing = false
                    self?.runState = .failed
                }
            }
        }
    }

    private func handleAIVideoOutputChunk(_ chunk: String) {
        outputBuffer += chunk
        appendAIVideoLogs(chunk)

        let normalized = chunk.replacingOccurrences(of: "\r", with: "\n")
        aiOutputPendingBuffer += normalized

        var lines = aiOutputPendingBuffer.components(separatedBy: .newlines)
        aiOutputPendingBuffer = lines.popLast() ?? ""

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmed.isEmpty {
                continue
            }
            handleAIVideoOutputLine(trimmed)
        }
    }

    private func handleAIVideoOutputLine(_ line: String) {
        if line.hasPrefix("PROGRESS:") {
            let message = line.replacingOccurrences(of: "PROGRESS:", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
            progressText = message
        }

        if line.hasPrefix("AI_VIDEO_GENERATED:") {
            aiVideoGeneratedSeen = true
            let fileName = line.replacingOccurrences(of: "AI_VIDEO_GENERATED:", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
            appendFeed("AI video generated: \(fileName)", level: .success)
        }

        if parseAIVideoClipJSONLine(line) {
            aiVideoPayloadSeen = true
        }

        if line.hasPrefix("DONE:") {
            aiVideoDoneSeen = true
        }

        if isFatalAIVideoLine(line) {
            sawErrorOutput = true
        }
    }

    private func appendAIVideoLogs(_ chunk: String) {
        // MoviePy progress updates are extremely noisy and can swamp the UI log view.
        if chunk.contains("now=None") && chunk.contains("t:") {
            return
        }

        let normalized = chunk.replacingOccurrences(of: "\r", with: "\n")
        logs += normalized

        let maxLogSize = 200_000
        if logs.count > maxLogSize {
            logs = String(logs.suffix(maxLogSize))
        }
    }

    @discardableResult
    private func parseAIVideoClipJSONLine(_ line: String) -> Bool {
        guard line.hasPrefix("AI_VIDEO_JSON:") else {
            return false
        }

        let jsonString = line.replacingOccurrences(of: "AI_VIDEO_JSON:", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
        guard let data = jsonString.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return false
        }

        handleAIVideoClipJSON(json)
        return true
    }

    private func parseAIVideoClipJSONFromOutputBuffer() {
        guard !aiVideoPayloadSeen else {
            return
        }

        let lines = outputBuffer.replacingOccurrences(of: "\r", with: "\n").components(separatedBy: .newlines)
        for line in lines {
            if parseAIVideoClipJSONLine(line.trimmingCharacters(in: .whitespacesAndNewlines)) {
                aiVideoPayloadSeen = true
                return
            }
        }
    }

    private func isFatalAIVideoLine(_ line: String) -> Bool {
        let lower = line.lowercased()

        // Warnings, fallback notices, and intermediate errors are non-fatal.
        // The primary AI generator may fail and emit errors, but the backend
        // fallback renderer can still succeed — only treat the final structured
        // ERROR: prefix from main.py as fatal.
        if lower.hasPrefix("warning ") || line.contains("⚠️") {
            return false
        }
        if lower.contains("shortform ai validation failed, using local fallback") {
            return false
        }
        if lower.hasPrefix("progress:") {
            return false
        }

        // Only the final structured error line from the backend is truly fatal.
        if lower.hasPrefix("error:") { return true }
        if lower.contains("failed to start ai video generation") { return true }

        return false
    }

    private func handleAIVideoClipJSON(_ json: [String: Any]) {
        guard let videoId = json["videoId"] as? Int,
              let fileName = json["fileName"] as? String,
              let path = json["path"] as? String,
              let status = json["status"] as? String else {
            return
        }

        let durationInt: Int = {
            if let value = json["duration"] as? Int {
                return value
            }
            if let value = json["duration"] as? String, let parsed = Int(value) {
                return parsed
            }
            return 0
        }()
        let size = json["size"] as? String ?? "0 B"

        let clip = Clip(
            videoId: videoId,
            fileName: fileName,
            duration: durationInt,
            size: size,
            path: path,
            status: status,
            uploadStatus: nil,
            retryCount: nil
        )

        if !generatedClips.contains(where: { $0.videoId == clip.videoId }) {
            generatedClips.append(clip)
        }
    }

    private func handleAIVideoExit(_ exitCode: Int32) {
        processExitCode = exitCode
        isProcessing = false
        parseAIVideoClipJSONFromOutputBuffer()
        if outputBuffer.contains("AI_VIDEO_GENERATED:") {
            aiVideoGeneratedSeen = true
        }
        if outputBuffer.contains("DONE: AI video generation complete") {
            aiVideoDoneSeen = true
        }
        let sawSuccessMarker = aiVideoGeneratedSeen || aiVideoPayloadSeen || aiVideoDoneSeen

        if didRequestStop {
            runState = .stopped
            progressText = "Stopped"
            appendFeed("AI video generation stopped by user.", level: .warning)
        } else if sawSuccessMarker || (exitCode == 0 && !sawErrorOutput) {
            runState = .succeeded
            progressText = "AI video generated successfully"
            progressValue = 1.0
            lastRunAt = Date()
            let summary = "AI video: \(aiVideoTheme.rawValue) \(aiVideoDuration.rawValue)s \(aiVideoType.rawValue)"
            lastRunSummary = "\(summary) at \(lastRunAt!.formatted(date: .abbreviated, time: .shortened))"
            appendFeed("AI video generation completed successfully.", level: .success)
            if exitCode != 0 {
                appendFeed("Process exited with code \(exitCode) after success markers. Marking run as successful.", level: .warning)
            }

            // Refresh clips from backend
            Task {
                try await Task.sleep(for: .seconds(1))
                await MainActor.run {
                    self.refreshGeneratedClipsFromBackend()
                }
            }
        } else {
            runState = .failed
            progressText = "AI video generation failed"
            progressValue = nil
            appendFeed("AI video generation failed with exit code \(exitCode).", level: .error)

            if sawErrorOutput {
                appendFeed("Check the output log for detailed error messages.", level: .warning)
            }
        }
    }

    func applySuggestedCaption(for clip: Clip?) {
        let trimmedTags = postHashtags.trimmingCharacters(in: .whitespacesAndNewlines)

        guard let clip else {
            postCaptionDraft = ""
            return
        }

        let hook = captionHook(for: contentTheme)
        var lines: [String] = [
            hook,
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

        if let path = clip.path {
            queueVideoBackend(path: path, caption: caption)
        }

        postStatusText = "Queued \(clip.fileName) for posting."
        appendFeed("Queued \(clip.fileName) for upload queue.", level: .success)
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
        guard let videoPath, !videoPath.isEmpty else {
            postStatusText = "No video selected for upload."
            appendFeed("Upload failed: no video selected", level: .error)
            return
        }

        guard FileManager.default.fileExists(atPath: videoPath) else {
            postStatusText = "Video file not found: \(videoPath)"
            appendFeed("Upload failed: video file not found", level: .error)
            return
        }

        var args = [
            "--video", videoPath,
            "--content-theme", contentTheme.rawValue,
            "--clip-format", clipFormat.rawValue
        ]

        if let caption, !caption.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            args += ["--caption", caption]
        }

        postStatusText = "Generating caption, rendering, queueing, and uploading..."
        appendFeed("Upload pipeline started for \(URL(fileURLWithPath: videoPath).lastPathComponent)", level: .info)

        runUploadScript(arguments: args) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let output):
                if output.contains("\"upload_status\": \"posted\"") {
                    self.postStatusText = "Video posted to TikTok."
                    self.appendFeed("TikTok upload completed.", level: .success)
                    self.markQueueItemPostedIfMatchingPath(videoPath)
                } else {
                    self.postStatusText = "Upload queued or in progress."
                    self.appendFeed("Upload queued. Worker will continue processing.", level: .info)
                }
                self.refreshGeneratedClipsFromBackend()
            case .failure(let error):
                self.postStatusText = "Upload failed"
                self.appendFeed("Upload failed: \(error.localizedDescription)", level: .error)
                self.refreshGeneratedClipsFromBackend()
            }
        }
    }

    func retryClipUpload(_ clip: Clip?) {
        guard let clip, let path = clip.path else {
            postStatusText = "Select a clip with a valid path to retry."
            return
        }

        postStatusText = "Retrying upload..."
        runUploadScript(arguments: ["--retry-video", path]) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success:
                self.postStatusText = "Retry submitted."
                self.appendFeed("Retry submitted for \(clip.fileName)", level: .info)
            case .failure(let error):
                self.postStatusText = "Retry failed"
                self.appendFeed("Retry failed: \(error.localizedDescription)", level: .error)
            }
            self.refreshGeneratedClipsFromBackend()
        }
    }

    func deleteClip(_ clip: Clip?) {
        guard let clip, let path = clip.path else {
            postStatusText = "Select a clip with a valid path to delete."
            return
        }

        postStatusText = "Deleting clip..."
        runUploadScript(arguments: ["--delete-video", path]) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success:
                self.postStatusText = "Deleted \(clip.fileName)."
                self.appendFeed("Deleted \(clip.fileName)", level: .warning)
                self.postQueue.removeAll { $0.clipPath == path }
                self.savePostState()
            case .failure(let error):
                self.postStatusText = "Delete failed"
                self.appendFeed("Delete failed: \(error.localizedDescription)", level: .error)
            }
            self.refreshGeneratedClipsFromBackend()
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

    func refreshGeneratedClipsFromBackend() {
        featuresService.listVideos { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let records):
                self.generatedClips = records.map { record in
                    let path = record.path
                    let size = self.fileSizeLabel(for: path)
                    return Clip(
                        videoId: record.id,
                        fileName: record.filename,
                        duration: self.estimatedDuration(from: path),
                        size: size,
                        path: path,
                        status: record.status,
                        uploadStatus: record.uploadStatus,
                        retryCount: record.retryCount
                    )
                }
                if self.generatedClips.count == 1 && self.postCaptionDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    self.applySuggestedCaption(for: self.generatedClips[0])
                }
            case .failure(let error):
                self.appendFeed("Failed to refresh video library: \(error.localizedDescription)", level: .warning)
            }
        }
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
                            size: "—",
                            status: "ready")
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

        if trimmed.contains("shortform ") {
            parseShortformLog(trimmed)
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
        guard let range = line.range(of: #"Step\s+(\d+)\s*/\s*(\d+)"#, options: .regularExpression) else {
            return nil
        }

        let match = String(line[range])
        let numbers = match.components(separatedBy: CharacterSet.decimalDigits.inverted).compactMap { Int($0) }
        guard numbers.count >= 2 else { return nil }
        return (numbers[0], numbers[1])
    }

    private func parseShortformLog(_ line: String) {
        shortformDetectedThisRun = true

        if line.contains("shortform optimization failed") {
            shortformLastError = line
            appendFeed("Shortform AI failed; fallback to original render.", level: .warning)
            return
        }

        if line.contains("shortform AI validation failed") {
            shortformLastError = line
            appendFeed("Shortform AI API unavailable; local validation fallback used.", level: .warning)
            return
        }

        if line.contains("shortform corrections applied="),
           let range = line.range(of: "shortform corrections applied=") {
            shortformLastCorrections = String(line[range.upperBound...]).trimmingCharacters(in: .whitespaces)
            return
        }

        guard line.contains("shortform validation source=") else {
            return
        }

        let source = extractCapture(from: line, pattern: #"source=([a-zA-Z_]+)"#, group: 1) ?? "unknown"
        let aesthetic = Int(extractCapture(from: line, pattern: #"aesthetic_score=(\d+)"#, group: 1) ?? "")
        let engagement = Int(extractCapture(from: line, pattern: #"engagement_score=(\d+)"#, group: 1) ?? "")

        shortformLastValidationSource = source
        shortformLastAestheticScore = aesthetic
        shortformLastEngagementScore = engagement

        if let aesthetic, let engagement {
            let level: FeedLevel = (aesthetic >= shortformAestheticThreshold && engagement >= shortformEngagementThreshold) ? .success : .warning
            appendFeed(
                "Shortform AI score A\(aesthetic) E\(engagement) (\(source)).",
                level: level
            )
        }
    }

    private func extractCapture(from input: String, pattern: String, group: Int) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern) else {
            return nil
        }
        let range = NSRange(input.startIndex..<input.endIndex, in: input)
        guard let match = regex.firstMatch(in: input, options: [], range: range),
              match.numberOfRanges > group,
              let valueRange = Range(match.range(at: group), in: input) else {
            return nil
        }
        return String(input[valueRange])
    }

    private func parseClipJSON(_ line: String) {
        let jsonString = line.replacingOccurrences(of: "CLIP_JSON:", with: "")
            .trimmingCharacters(in: .whitespaces)

        guard let data = jsonString.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }

        let fileName = object["fileName"] as? String ?? "Clip \(generatedClips.count + 1)"
        let duration = object["duration"] as? Int ?? clipDuration
        let size = object["size"] as? String ?? "—"
        let path = object["path"] as? String
        let status = object["status"] as? String ?? "ready"
        let videoId = object["videoId"] as? Int

        upsertClip(
            Clip(
                videoId: videoId,
                fileName: fileName,
                duration: duration,
                size: size,
                path: path,
                status: status
            )
        )
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
        if let index = generatedClips.firstIndex(where: { ($0.path ?? $0.fileName) == (clip.path ?? clip.fileName) }) {
            generatedClips[index] = clip
        } else {
            generatedClips.append(clip)
        }

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

    private func ensureStorageDirectoryExists() throws {
        try FileManager.default.createDirectory(
            at: queueStorageURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
    }

    private func queueVideoBackend(path: String, caption: String) {
        var args = [
            "--video", path,
            "--queue-only",
            "--content-theme", contentTheme.rawValue,
            "--clip-format", clipFormat.rawValue
        ]

        if !caption.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            args += ["--caption", caption]
        }

        runUploadScript(arguments: args) { [weak self] result in
            guard let self else { return }
            switch result {
            case .success:
                self.refreshGeneratedClipsFromBackend()
            case .failure(let error):
                self.appendFeed("Failed to enqueue upload: \(error.localizedDescription)", level: .warning)
            }
        }
    }

    private func markQueueItemPostedIfMatchingPath(_ path: String) {
        guard let item = postQueue.first(where: { $0.clipPath == path }) else { return }
        markQueueItemPosted(item)
    }

    private func runUploadScript(arguments: [String], completion: @escaping (Result<String, Error>) -> Void) {
        guard let scriptPath = Self.uploadScriptPath() else {
            completion(.failure(NSError(
                domain: "TikTokUpload",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Upload script not found"]
            )))
            return
        }

        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = [scriptPath] + arguments

            let outputPipe = Pipe()
            let errorPipe = Pipe()
            process.standardOutput = outputPipe
            process.standardError = errorPipe

            do {
                try process.run()
                process.waitUntilExit()

                let outputData = outputPipe.fileHandleForReading.readDataToEndOfFile()
                let errorData = errorPipe.fileHandleForReading.readDataToEndOfFile()

                let output = String(data: outputData, encoding: .utf8) ?? ""
                let errorOutput = String(data: errorData, encoding: .utf8) ?? ""
                let combined = [output, errorOutput].joined(separator: "\n")

                DispatchQueue.main.async {
                    if process.terminationStatus == 0 {
                        completion(.success(combined))
                    } else {
                        completion(.failure(NSError(
                            domain: "TikTokUpload",
                            code: Int(process.terminationStatus),
                            userInfo: [NSLocalizedDescriptionKey: combined.isEmpty ? "Upload process failed" : combined]
                        )))
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    completion(.failure(error))
                }
            }
        }
    }

    private func startUploadWorker() {
        guard uploadWorkerProcess == nil else { return }
        guard let scriptPath = Self.uploadScriptPath() else {
            appendFeed("Upload worker script missing; queue resume disabled.", level: .warning)
            return
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [scriptPath, "--worker"]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice

        do {
            try process.run()
            uploadWorkerProcess = process
            appendFeed("Upload worker started. Queue resumes automatically on restart.", level: .info)
        } catch {
            appendFeed("Failed to start upload worker: \(error.localizedDescription)", level: .warning)
        }
    }

    private static func uploadScriptPath() -> String? {
        let devPath = NSHomeDirectory() + "/TikTokUploadManager/Python/tiktok_upload_cli.py"
        if FileManager.default.fileExists(atPath: devPath) {
            return devPath
        }

        if let bundledPath = Bundle.main.path(forResource: "tiktok_upload_cli", ofType: "py") {
            return bundledPath
        }

        return nil
    }

    private func fileSizeLabel(for path: String?) -> String {
        guard let path, FileManager.default.fileExists(atPath: path),
              let attrs = try? FileManager.default.attributesOfItem(atPath: path),
              let bytes = attrs[.size] as? Int64 else {
            return "—"
        }

        let size = Double(bytes)
        if size < 1024 {
            return "\(Int(size)) B"
        }
        let kb = size / 1024
        if kb < 1024 {
            return String(format: "%.1f KB", kb)
        }
        let mb = kb / 1024
        if mb < 1024 {
            return String(format: "%.1f MB", mb)
        }
        return String(format: "%.2f GB", mb / 1024)
    }

    private func estimatedDuration(from path: String?) -> Int {
        guard let path,
              FileManager.default.fileExists(atPath: path) else {
            return clipDuration
        }

        let asset = AVURLAsset(url: URL(fileURLWithPath: path))
        let seconds = CMTimeGetSeconds(asset.duration)
        if seconds.isFinite && seconds > 0 {
            return Int(seconds.rounded())
        }
        return clipDuration
    }
}
