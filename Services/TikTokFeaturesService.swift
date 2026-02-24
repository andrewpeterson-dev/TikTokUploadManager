import Foundation

final class TikTokFeaturesService {

    private let pythonExecutableURL: URL
    private let featuresScriptURL: URL
    private let uploadScriptURL: URL

    enum Feature {
        case status
        case backgrounds
        case downloadBackgrounds
        case addAccount(username: String, niche: String, name: String)
        case listAccounts(niche: String?)
        case analytics(username: String?)

        var command: String {
            switch self {
            case .status: return "status"
            case .backgrounds: return "backgrounds"
            case .downloadBackgrounds: return "download-backgrounds"
            case .addAccount: return "add-account"
            case .listAccounts: return "list-accounts"
            case .analytics: return "analytics"
            }
        }

        var arguments: [String] {
            var args = [command]
            switch self {
            case .addAccount(let username, let niche, let name):
                args += ["--username", username, "--niche", niche, "--name", name]
            case .listAccounts(let niche):
                if let niche {
                    args += ["--niche", niche]
                }
            case .analytics(let username):
                if let username {
                    args += ["--username", username]
                }
            default:
                break
            }
            return args
        }
    }

    struct BackgroundInfo: Identifiable, Codable {
        let id = UUID()
        let name: String
        let path: String
        let theme: String?

        enum CodingKeys: String, CodingKey {
            case name, path, theme
        }
    }

    struct AccountInfo: Identifiable, Codable {
        let id: String
        let username: String
        let displayName: String
        let niche: String
        let status: String
        let followers: Int
        let totalViews: Int
        let totalLikes: Int
        let totalPosts: Int
    }

    struct Analytics: Codable {
        let totalViews: Int
        let totalLikes: Int
        let totalPosts: Int
        let activeAccounts: Int?
        let followerGrowth: Int?
    }

    struct AuthStatus: Codable {
        let connected: Bool
        let expiresAt: String?
        let secondsRemaining: Int
        let scope: String?
    }

    struct VideoRecord: Identifiable, Codable {
        let id: Int
        let filename: String
        let sourcePath: String?
        let exportPath: String?
        let caption: String?
        let status: String
        let createdAt: String
        let uploadId: Int?
        let uploadStatus: String?
        let retryCount: Int?
        let lastAttempt: String?
        let errorMessage: String?

        var path: String? {
            if let exportPath, !exportPath.isEmpty {
                return exportPath
            }
            return sourcePath
        }

        enum CodingKeys: String, CodingKey {
            case id
            case filename
            case sourcePath = "source_path"
            case exportPath = "export_path"
            case caption
            case status
            case createdAt = "created_at"
            case uploadId = "upload_id"
            case uploadStatus = "upload_status"
            case retryCount = "retry_count"
            case lastAttempt = "last_attempt"
            case errorMessage = "error_message"
        }
    }

    init(pythonExecutableURL: URL? = nil, featuresScriptURL: URL? = nil, uploadScriptURL: URL? = nil) {
        self.pythonExecutableURL = pythonExecutableURL ?? Self.defaultPythonExecutableURL()
        self.featuresScriptURL = featuresScriptURL ?? Self.defaultFeaturesScriptURL()
        self.uploadScriptURL = uploadScriptURL ?? Self.defaultUploadScriptURL()
    }

    func getStatus(completion: @escaping (Result<String, Error>) -> Void) {
        runFeature(.status, completion: completion)
    }

    func listBackgrounds(completion: @escaping (Result<[BackgroundInfo], Error>) -> Void) {
        runFeature(.backgrounds) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let output):
                    completion(.success(self.parseBackgrounds(from: output)))
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }

    func downloadBackgrounds(progressHandler: @escaping (String) -> Void, completion: @escaping (Result<String, Error>) -> Void) {
        runFeatureWithProgress(.downloadBackgrounds, progressHandler: progressHandler, completion: completion)
    }

    func addAccount(username: String, niche: String, name: String, completion: @escaping (Result<String, Error>) -> Void) {
        runFeature(.addAccount(username: username, niche: niche, name: name), completion: completion)
    }

    func listAccounts(niche: String? = nil, completion: @escaping (Result<[AccountInfo], Error>) -> Void) {
        runFeature(.listAccounts(niche: niche)) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let output):
                    completion(.success(self.parseAccounts(from: output)))
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }

    func getAnalytics(username: String? = nil, completion: @escaping (Result<Analytics, Error>) -> Void) {
        runFeature(.analytics(username: username)) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let output):
                    if let analytics = self.parseAnalytics(from: output) {
                        completion(.success(analytics))
                    } else {
                        completion(.failure(NSError(
                            domain: "TikTokFeatures",
                            code: -1,
                            userInfo: [NSLocalizedDescriptionKey: "Failed to parse analytics"]
                        )))
                    }
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }

    func connectTikTok(completion: @escaping (Result<AuthStatus, Error>) -> Void) {
        runUploadCommand(arguments: ["--oauth-connect"]) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let output):
                    if let status = self.parseAuthStatus(from: output) {
                        completion(.success(status))
                    } else {
                        completion(.failure(NSError(
                            domain: "TikTokFeatures",
                            code: -2,
                            userInfo: [NSLocalizedDescriptionKey: "Failed to parse OAuth response"]
                        )))
                    }
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }

    func getTikTokAuthStatus(completion: @escaping (Result<AuthStatus, Error>) -> Void) {
        runUploadCommand(arguments: ["--oauth-status"]) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let output):
                    if let status = self.parseAuthStatus(from: output) {
                        completion(.success(status))
                    } else {
                        completion(.failure(NSError(
                            domain: "TikTokFeatures",
                            code: -3,
                            userInfo: [NSLocalizedDescriptionKey: "Failed to parse OAuth status"]
                        )))
                    }
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }

    func listVideos(completion: @escaping (Result<[VideoRecord], Error>) -> Void) {
        runUploadCommand(arguments: ["--list-videos-json"]) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let output):
                    completion(.success(self.parseVideoRecords(from: output)))
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }

    func retryVideo(path: String, completion: @escaping (Result<String, Error>) -> Void) {
        runUploadCommand(arguments: ["--retry-video", path], completion: completion)
    }

    func deleteVideo(path: String, completion: @escaping (Result<String, Error>) -> Void) {
        runUploadCommand(arguments: ["--delete-video", path], completion: completion)
    }

    private func runFeature(_ feature: Feature, completion: @escaping (Result<String, Error>) -> Void) {
        runFeatureWithProgress(feature, progressHandler: { _ in }, completion: completion)
    }

    private func runFeatureWithProgress(
        _ feature: Feature,
        progressHandler: @escaping (String) -> Void,
        completion: @escaping (Result<String, Error>) -> Void
    ) {
        runScript(
            scriptURL: featuresScriptURL,
            arguments: feature.arguments,
            progressHandler: progressHandler,
            completion: completion
        )
    }

    private func runUploadCommand(arguments: [String], completion: @escaping (Result<String, Error>) -> Void) {
        runScript(
            scriptURL: uploadScriptURL,
            arguments: arguments,
            progressHandler: { _ in },
            completion: completion
        )
    }

    private func runScript(
        scriptURL: URL,
        arguments: [String],
        progressHandler: @escaping (String) -> Void,
        completion: @escaping (Result<String, Error>) -> Void
    ) {
        guard FileManager.default.fileExists(atPath: scriptURL.path) else {
            let error = NSError(
                domain: "TikTokFeatures",
                code: -1,
                userInfo: [NSLocalizedDescriptionKey: "Script not found: \(scriptURL.path)"]
            )
            completion(.failure(error))
            return
        }

        let process = Process()
        let pipe = Pipe()

        process.executableURL = pythonExecutableURL
        process.arguments = [scriptURL.path] + arguments
        // Set working directory to project root (not Python/ subdirectory)
        // This allows Python imports to work correctly
        process.currentDirectoryURL = scriptURL.deletingLastPathComponent().deletingLastPathComponent()
        process.standardOutput = pipe
        process.standardError = pipe

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"

        // Ensure ffmpeg and other tools are in PATH
        let homeDir = FileManager.default.homeDirectoryForCurrentUser.path
        let userBinPath = "\(homeDir)/bin"
        let brewBinPath = "/opt/homebrew/bin"
        let usrLocalBin = "/usr/local/bin"

        if let existingPath = environment["PATH"] {
            environment["PATH"] = "\(userBinPath):\(brewBinPath):\(usrLocalBin):\(existingPath)"
        } else {
            environment["PATH"] = "\(userBinPath):\(brewBinPath):\(usrLocalBin):/usr/bin:/bin"
        }

        process.environment = environment

        var outputData = Data()

        pipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            outputData.append(data)
            if let output = String(data: data, encoding: .utf8), !output.isEmpty {
                DispatchQueue.main.async {
                    progressHandler(output)
                }
            }
        }

        process.terminationHandler = { process in
            pipe.fileHandleForReading.readabilityHandler = nil
            let output = String(data: outputData, encoding: .utf8) ?? ""
            DispatchQueue.main.async {
                if process.terminationStatus == 0 {
                    completion(.success(output))
                } else {
                    let error = NSError(
                        domain: "TikTokFeatures",
                        code: Int(process.terminationStatus),
                        userInfo: [NSLocalizedDescriptionKey: "Process failed (\(process.terminationStatus)): \(output)"]
                    )
                    completion(.failure(error))
                }
            }
        }

        do {
            try process.run()
        } catch {
            completion(.failure(error))
        }
    }

    private func parseBackgrounds(from output: String) -> [BackgroundInfo] {
        var backgrounds: [BackgroundInfo] = []
        let lines = output.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard trimmed.hasPrefix("- ") else { continue }
            let name = String(trimmed.dropFirst(2)).trimmingCharacters(in: .whitespaces)
            guard !name.isEmpty else { continue }
            let theme = inferTheme(from: name)
            backgrounds.append(BackgroundInfo(name: name, path: name, theme: theme))
        }
        return backgrounds
    }

    private func parseAccounts(from output: String) -> [AccountInfo] {
        var accounts: [AccountInfo] = []
        let lines = output.components(separatedBy: .newlines)

        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard trimmed.hasPrefix("@") else { continue }
            let components = trimmed.components(separatedBy: " - ")
            guard components.count >= 3 else { continue }

            let username = String(components[0].dropFirst())
            let niche = components[1]
            let status = components[2]
            let followers = components.count > 3 ? extractNumber(from: components[3]) : 0

            accounts.append(AccountInfo(
                id: username,
                username: username,
                displayName: username,
                niche: niche,
                status: status,
                followers: followers,
                totalViews: 0,
                totalLikes: 0,
                totalPosts: 0
            ))
        }

        return accounts
    }

    private func parseAnalytics(from output: String) -> Analytics? {
        var totalViews = 0
        var totalLikes = 0
        var totalPosts = 0
        var activeAccounts: Int? = nil
        var followerGrowth: Int? = nil

        let lines = output.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            if trimmed.contains("total_views:") {
                totalViews = extractNumber(from: trimmed)
            } else if trimmed.contains("total_likes:") {
                totalLikes = extractNumber(from: trimmed)
            } else if trimmed.contains("total_posts:") {
                totalPosts = extractNumber(from: trimmed)
            } else if trimmed.contains("active_accounts:") {
                activeAccounts = extractNumber(from: trimmed)
            } else if trimmed.contains("follower_growth:") {
                followerGrowth = extractNumber(from: trimmed)
            }
        }

        return Analytics(
            totalViews: totalViews,
            totalLikes: totalLikes,
            totalPosts: totalPosts,
            activeAccounts: activeAccounts,
            followerGrowth: followerGrowth
        )
    }

    private func parseAuthStatus(from output: String) -> AuthStatus? {
        guard let json = extractJSONLine(prefix: "AUTH_JSON:", from: output),
              let data = json.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return nil
        }

        let connected = object["connected"] as? Bool ?? false
        let expiresAt = object["expires_at"] as? String
        let secondsRemaining = object["seconds_remaining"] as? Int ?? 0
        let scope = object["scope"] as? String

        return AuthStatus(
            connected: connected,
            expiresAt: expiresAt,
            secondsRemaining: secondsRemaining,
            scope: scope
        )
    }

    private func parseVideoRecords(from output: String) -> [VideoRecord] {
        guard let json = extractJSONLine(prefix: "VIDEOS_JSON:", from: output),
              let data = json.data(using: .utf8),
              let records = try? JSONDecoder().decode([VideoRecord].self, from: data) else {
            return []
        }
        return records
    }

    private func extractJSONLine(prefix: String, from output: String) -> String? {
        let lines = output.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard trimmed.hasPrefix(prefix) else { continue }
            return String(trimmed.dropFirst(prefix.count)).trimmingCharacters(in: .whitespaces)
        }
        return nil
    }

    private func extractNumber(from string: String) -> Int {
        let cleaned = string.components(separatedBy: CharacterSet.decimalDigits.inverted).joined()
        return Int(cleaned) ?? 0
    }

    private func inferTheme(from filename: String) -> String? {
        let lower = filename.lowercased()
        if lower.contains("gta") || lower.contains("game") { return "gaming" }
        if lower.contains("subway") { return "subway" }
        if lower.contains("satisfying") { return "satisfying" }
        if lower.contains("dating") { return "dating" }
        if lower.contains("motiv") { return "motivational" }
        return nil
    }

    private static func defaultPythonExecutableURL() -> URL {
        let env = ProcessInfo.processInfo.environment
        if let configured = env["TIKTOK_PYTHON_EXECUTABLE"], !configured.isEmpty {
            return URL(fileURLWithPath: configured)
        }

        let candidates = [
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3"
        ]

        for candidate in candidates {
            if FileManager.default.fileExists(atPath: candidate) {
                return URL(fileURLWithPath: candidate)
            }
        }

        return URL(fileURLWithPath: "/usr/bin/python3")
    }

    private static func defaultFeaturesScriptURL() -> URL {
        let fileManager = FileManager.default

        if let bundledScript = Bundle.main.resourceURL?.appendingPathComponent("Python/tiktok_features.py"),
           fileManager.fileExists(atPath: bundledScript.path) {
            return bundledScript
        }

        return URL(fileURLWithPath: "\(NSHomeDirectory())/TikTokUploadManager/Python/tiktok_features.py")
    }

    private static func defaultUploadScriptURL() -> URL {
        let fileManager = FileManager.default

        if let bundledScript = Bundle.main.resourceURL?.appendingPathComponent("Python/tiktok_upload_cli.py"),
           fileManager.fileExists(atPath: bundledScript.path) {
            return bundledScript
        }

        return URL(fileURLWithPath: "\(NSHomeDirectory())/TikTokUploadManager/Python/tiktok_upload_cli.py")
    }
}
