import SwiftUI
import Foundation

@MainActor
final class FeaturesViewModel: ObservableObject {

    @Published var accounts: [TikTokFeaturesService.AccountInfo] = []
    @Published var backgrounds: [TikTokFeaturesService.BackgroundInfo] = []
    @Published var analytics: TikTokFeaturesService.Analytics?

    @Published var isLoading = false
    @Published var statusMessage = ""
    @Published var errorMessage: String?

    private let service = TikTokFeaturesService()

    // MARK: - Accounts

    func loadAccounts(niche: String? = nil) {
        isLoading = true
        statusMessage = "Loading accounts..."
        errorMessage = nil

        service.listAccounts(niche: niche) { [weak self] result in
            guard let self = self else { return }
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
            guard let self = self else { return }
            self.isLoading = false

            switch result {
            case .success:
                self.statusMessage = "✅ Added @\(username)"
                // Reload accounts
                self.loadAccounts()
            case .failure(let error):
                self.errorMessage = "Failed to add account: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        }
    }

    // MARK: - Backgrounds

    func loadBackgrounds() {
        isLoading = true
        statusMessage = "Loading backgrounds..."
        errorMessage = nil

        service.listBackgrounds { [weak self] result in
            guard let self = self else { return }
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
        statusMessage = "Downloading backgrounds..."
        errorMessage = nil

        service.downloadBackgrounds(progressHandler: { [weak self] output in
            guard let self = self else { return }
            // Show download progress
            self.statusMessage = output.trimmingCharacters(in: .whitespacesAndNewlines)
        }, completion: { [weak self] result in
            guard let self = self else { return }
            self.isLoading = false

            switch result {
            case .success:
                self.statusMessage = "✅ Download complete"
                // Reload backgrounds
                self.loadBackgrounds()
            case .failure(let error):
                self.errorMessage = "Download failed: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        })
    }

    // MARK: - Analytics

    func loadAnalytics(username: String? = nil) {
        isLoading = true
        statusMessage = username != nil ? "Loading analytics for @\(username!)..." : "Loading overall analytics..."
        errorMessage = nil

        service.getAnalytics(username: username) { [weak self] result in
            guard let self = self else { return }
            self.isLoading = false

            switch result {
            case .success(let analytics):
                self.analytics = analytics
                self.statusMessage = "✅ Analytics loaded"
            case .failure(let error):
                self.errorMessage = "Failed to load analytics: \(error.localizedDescription)"
                self.statusMessage = ""
            }
        }
    }

    // MARK: - Status

    func refreshStatus() {
        isLoading = true
        statusMessage = "Checking feature status..."
        errorMessage = nil

        service.getStatus { [weak self] result in
            guard let self = self else { return }
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

    // MARK: - Utility

    func clearError() {
        errorMessage = nil
    }
}
