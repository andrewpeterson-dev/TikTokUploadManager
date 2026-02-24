import Foundation

/// Service for interacting with enhanced TikTok features (backgrounds, accounts, analytics)
final class TikTokFeaturesService {

    private let pythonExecutableURL: URL
    private let featuresScriptURL: URL

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
                if let niche = niche {
                    args += ["--niche", niche]
                }
            case .analytics(let username):
                if let username = username {
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

    init(pythonExecutableURL: URL? = nil, featuresScriptURL: URL? = nil) {
        self.pythonExecutableURL = pythonExecutableURL ?? Self.defaultPythonExecutableURL()
        self.featuresScriptURL = featuresScriptURL ?? Self.defaultFeaturesScriptURL()
    }

    // MARK: - Main API Methods

    func getStatus(completion: @escaping (Result<String, Error>) -> Void) {
        runFeature(.status) { result in
            DispatchQueue.main.async {
                completion(result)
            }
        }
    }

    func listBackgrounds(completion: @escaping (Result<[BackgroundInfo], Error>) -> Void) {
        runFeature(.backgrounds) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let output):
                    // Parse background list from output
                    let backgrounds = self.parseBackgrounds(from: output)
                    completion(.success(backgrounds))
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }

    func downloadBackgrounds(progressHandler: @escaping (String) -> Void, completion: @escaping (Result<String, Error>) -> Void) {
        runFeatureWithProgress(.downloadBackgrounds, progressHandler: progressHandler) { result in
            DispatchQueue.main.async {
                completion(result)
            }
        }
    }

    func addAccount(username: String, niche: String, name: String, completion: @escaping (Result<String, Error>) -> Void) {
        runFeature(.addAccount(username: username, niche: niche, name: name)) { result in
            DispatchQueue.main.async {
                completion(result)
            }
        }
    }

    func listAccounts(niche: String? = nil, completion: @escaping (Result<[AccountInfo], Error>) -> Void) {
        runFeature(.listAccounts(niche: niche)) { result in
            DispatchQueue.main.async {
                switch result {
                case .success(let output):
                    let accounts = self.parseAccounts(from: output)
                    completion(.success(accounts))
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
                        completion(.failure(NSError(domain: "TikTokFeatures", code: -1, userInfo: [NSLocalizedDescriptionKey: "Failed to parse analytics"])))
                    }
                case .failure(let error):
                    completion(.failure(error))
                }
            }
        }
    }

    // MARK: - Private Methods

    private func runFeature(_ feature: Feature, completion: @escaping (Result<String, Error>) -> Void) {
        runFeatureWithProgress(feature, progressHandler: { _ in }, completion: completion)
    }

    private func runFeatureWithProgress(_ feature: Feature, progressHandler: @escaping (String) -> Void, completion: @escaping (Result<String, Error>) -> Void) {
        print("🔍 [TikTokFeatures] Running feature: \(feature.command)")
        print("   Python: \(pythonExecutableURL.path)")
        print("   Script: \(featuresScriptURL.path)")
        print("   Args: \(feature.arguments)")

        guard FileManager.default.fileExists(atPath: featuresScriptURL.path) else {
            let error = "Features script not found at: \(featuresScriptURL.path)"
            print("❌ [TikTokFeatures] \(error)")
            completion(.failure(NSError(domain: "TikTokFeatures", code: -1, userInfo: [NSLocalizedDescriptionKey: error])))
            return
        }

        let process = Process()
        let pipe = Pipe()

        process.executableURL = pythonExecutableURL
        process.arguments = [featuresScriptURL.path] + feature.arguments
        process.currentDirectoryURL = featuresScriptURL.deletingLastPathComponent()
        process.standardOutput = pipe
        process.standardError = pipe

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment

        var outputData = Data()

        pipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            outputData.append(data)
            if let output = String(data: data, encoding: .utf8), !output.isEmpty {
                print("📝 [TikTokFeatures] Output: \(output.prefix(200))")
                DispatchQueue.main.async {
                    progressHandler(output)
                }
            }
        }

        process.terminationHandler = { process in
            let output = String(data: outputData, encoding: .utf8) ?? ""
            print("✅ [TikTokFeatures] Process completed with status \(process.terminationStatus)")
            print("   Output length: \(output.count) characters")

            if process.terminationStatus == 0 {
                completion(.success(output))
            } else {
                let error = "Process failed with status \(process.terminationStatus)\nOutput: \(output)"
                print("❌ [TikTokFeatures] \(error)")
                completion(.failure(NSError(domain: "TikTokFeatures", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: error])))
            }
        }

        do {
            try process.run()
            print("✅ [TikTokFeatures] Process started successfully")
        } catch {
            print("❌ [TikTokFeatures] Failed to start process: \(error.localizedDescription)")
            completion(.failure(error))
        }
    }

    // MARK: - Parsing Methods

    private func parseBackgrounds(from output: String) -> [BackgroundInfo] {
        var backgrounds: [BackgroundInfo] = []

        // Parse output looking for background filenames
        let lines = output.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            // Look for lines like "   - filename.mp4"
            if trimmed.hasPrefix("- ") || trimmed.hasPrefix("•") {
                let name = trimmed.dropFirst(2).trimmingCharacters(in: .whitespaces)
                if name.hasSuffix(".mp4") {
                    // Try to infer theme from filename
                    let theme = inferTheme(from: name)
                    backgrounds.append(BackgroundInfo(
                        name: name,
                        path: "", // Full path would be in backgrounds directory
                        theme: theme
                    ))
                }
            }
        }

        return backgrounds
    }

    private func parseAccounts(from output: String) -> [AccountInfo] {
        var accounts: [AccountInfo] = []

        print("🔍 [TikTokFeatures] Parsing accounts from output...")
        print("   Output: \(output.prefix(500))")

        // Parse output looking for account info
        // Format: @username - niche - status - X followers
        let lines = output.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("@") {
                print("   Found account line: \(trimmed)")
                let components = trimmed.components(separatedBy: " - ")
                if components.count >= 3 {
                    let username = String(components[0].dropFirst()) // Remove @
                    let niche = components[1].trimmingCharacters(in: .whitespaces)
                    let status = components[2].trimmingCharacters(in: .whitespaces)

                    // Try to extract follower count
                    var followers = 0
                    if components.count >= 4 {
                        let followerStr = components[3].components(separatedBy: " ").first ?? "0"
                        followers = Int(followerStr) ?? 0
                    }

                    let account = AccountInfo(
                        id: username,
                        username: username,
                        displayName: username,
                        niche: niche,
                        status: status,
                        followers: followers,
                        totalViews: 0,
                        totalLikes: 0,
                        totalPosts: 0
                    )
                    accounts.append(account)
                    print("   ✅ Parsed account: @\(username)")
                }
            }
        }

        print("✅ [TikTokFeatures] Parsed \(accounts.count) accounts")
        return accounts
    }

    private func parseAnalytics(from output: String) -> Analytics? {
        // Parse analytics output
        // Format: Lines like "Total Views: 1,234"
        var totalViews = 0
        var totalLikes = 0
        var totalPosts = 0
        var activeAccounts: Int? = nil
        var followerGrowth: Int? = nil

        let lines = output.components(separatedBy: .newlines)
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)

            if trimmed.contains("total_views:") || trimmed.contains("Total Views:") {
                let value = extractNumber(from: trimmed)
                totalViews = value
            } else if trimmed.contains("total_likes:") || trimmed.contains("Total Likes:") {
                let value = extractNumber(from: trimmed)
                totalLikes = value
            } else if trimmed.contains("total_posts:") || trimmed.contains("Total Posts:") {
                let value = extractNumber(from: trimmed)
                totalPosts = value
            } else if trimmed.contains("active_accounts:") || trimmed.contains("Active Accounts:") {
                let value = extractNumber(from: trimmed)
                activeAccounts = value
            } else if trimmed.contains("follower_growth:") || trimmed.contains("Follower Growth:") {
                let value = extractNumber(from: trimmed)
                followerGrowth = value
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

    private func extractNumber(from string: String) -> Int {
        // Extract first number from string, handling commas
        let cleaned = string.components(separatedBy: CharacterSet.decimalDigits.inverted).joined()
        return Int(cleaned) ?? 0
    }

    private func inferTheme(from filename: String) -> String? {
        let lower = filename.lowercased()
        if lower.contains("scary") || lower.contains("horror") { return "scary" }
        if lower.contains("dating") || lower.contains("romance") { return "dating" }
        if lower.contains("crazy") || lower.contains("wild") { return "crazy" }
        if lower.contains("mystery") { return "mystery" }
        if lower.contains("motivational") || lower.contains("inspire") { return "motivational" }
        if lower.contains("creepy") { return "creepy" }
        if lower.contains("interesting") || lower.contains("facts") { return "interesting" }
        return nil
    }

    // MARK: - Path Helpers

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

        // Check bundled resources first
        if let bundledScript = Bundle.main.resourceURL?.appendingPathComponent("Python/tiktok_features.py"),
           fileManager.fileExists(atPath: bundledScript.path) {
            return bundledScript
        }

        // Check project directory
        let projectScript = URL(fileURLWithPath: "\(NSHomeDirectory())/TikTokUploadManager/Python/tiktok_features.py")
        return projectScript
    }
}
