import SwiftUI
import Foundation

@MainActor
final class FeaturesViewModel: ObservableObject {

    @Published var accounts: [TikTokFeaturesService.AccountInfo] = []
    @Published var backgrounds: [TikTokFeaturesService.BackgroundInfo] = []
    @Published var analytics: TikTokFeaturesService.Analytics?
    @Published var authStatus = TikTokFeaturesService.AuthStatus(connected: false, expiresAt: nil, secondsRemaining: 0, scope: nil)

    @Published var isLoading = false
    @Published var statusMessage = ""
    @Published var errorMessage: String?

    private let service = TikTokFeaturesService()
    private var authCountdownTimer: Timer?

    init() {
        startAuthCountdownTimer()
    }

    deinit {
        authCountdownTimer?.invalidate()
    }

    func loadAccounts(niche: String? = nil) {
        isLoading = true
        statusMessage = "Loading accounts..."
        errorMessage = nil

        service.listAccounts(niche: niche) { [weak self] result in
            guard let self else { return }
            self.isLoading = false

            switch result {
            case .success(let accounts):
                self.accounts = accounts
                self.statusMessage = "Loaded \(accounts.count) account(s)"
            case .failure(let error):
                self.errorMessage = "Failed to load accounts: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        }
    }

    func addAccount(username: String, niche: String, name: String) {
        isLoading = true
        statusMessage = "Adding account @\(username)..."
        errorMessage = nil

        service.addAccount(username: username, niche: niche, name: name) { [weak self] result in
            guard let self else { return }
            self.isLoading = false

            switch result {
            case .success:
                self.statusMessage = "Added @\(username)"
                self.loadAccounts()
            case .failure(let error):
                self.errorMessage = "Failed to add account: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        }
    }

    func loadBackgrounds() {
        isLoading = true
        statusMessage = "Loading backgrounds..."
        errorMessage = nil

        service.listBackgrounds { [weak self] result in
            guard let self else { return }
            self.isLoading = false

            switch result {
            case .success(let backgrounds):
                self.backgrounds = backgrounds
                self.statusMessage = "Loaded \(backgrounds.count) background(s)"
            case .failure(let error):
                self.errorMessage = "Failed to load backgrounds: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        }
    }

    func downloadBackgrounds() {
        isLoading = true
        statusMessage = "Syncing backgrounds..."
        errorMessage = nil

        service.downloadBackgrounds(progressHandler: { [weak self] output in
            guard let self else { return }
            let trimmed = output.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty {
                self.statusMessage = trimmed
            }
        }, completion: { [weak self] result in
            guard let self else { return }
            self.isLoading = false

            switch result {
            case .success:
                self.statusMessage = "Background sync complete"
                self.loadBackgrounds()
            case .failure(let error):
                self.errorMessage = "Background sync failed: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        })
    }

    func loadAnalytics(username: String? = nil) {
        isLoading = true
        statusMessage = username != nil ? "Loading analytics for @\(username!)..." : "Loading overall analytics..."
        errorMessage = nil

        service.getAnalytics(username: username) { [weak self] result in
            guard let self else { return }
            self.isLoading = false

            switch result {
            case .success(let analytics):
                self.analytics = analytics
                self.statusMessage = "Analytics loaded"
            case .failure(let error):
                self.errorMessage = "Failed to load analytics: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        }
    }

    func refreshStatus() {
        isLoading = true
        statusMessage = "Checking feature status..."
        errorMessage = nil

        service.getStatus { [weak self] result in
            guard let self else { return }
            self.isLoading = false

            switch result {
            case .success(let status):
                self.statusMessage = status
            case .failure(let error):
                self.errorMessage = "Status check failed: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        }
    }

    func refreshTikTokAuthStatus() {
        service.getTikTokAuthStatus { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let status):
                self.authStatus = status
            case .failure(let error):
                self.errorMessage = "Failed to refresh TikTok auth: \(error.localizedDescription)"
            }
        }
    }

    func connectTikTok() {
        isLoading = true
        statusMessage = "Opening TikTok OAuth flow..."
        errorMessage = nil

        service.connectTikTok { [weak self] result in
            guard let self else { return }
            self.isLoading = false

            switch result {
            case .success(let status):
                self.authStatus = status
                self.statusMessage = status.connected ? "TikTok connected" : "TikTok not connected"
            case .failure(let error):
                self.errorMessage = "TikTok connect failed: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        }
    }

    func authCountdownLabel(now: Date = Date()) -> String {
        guard authStatus.connected, let expiresAt = authStatus.expiresAt else {
            return "Not Connected"
        }

        let formatter = ISO8601DateFormatter()
        guard let expiryDate = formatter.date(from: expiresAt) else {
            return "Connected"
        }

        let remaining = max(0, Int(expiryDate.timeIntervalSince(now)))
        let hours = remaining / 3600
        let minutes = (remaining % 3600) / 60
        let seconds = remaining % 60
        return String(format: "%02dh %02dm %02ds", hours, minutes, seconds)
    }

    func clearError() {
        errorMessage = nil
    }

    private func startAuthCountdownTimer() {
        authCountdownTimer?.invalidate()
        authCountdownTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                if self.authStatus.connected && self.authStatus.secondsRemaining > 0 {
                    self.authStatus = TikTokFeaturesService.AuthStatus(
                        connected: true,
                        expiresAt: self.authStatus.expiresAt,
                        secondsRemaining: max(0, self.authStatus.secondsRemaining - 1),
                        scope: self.authStatus.scope
                    )
                }
            }
        }
    }
}
