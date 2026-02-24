import SwiftUI
import AVKit
import AVFoundation

struct ContentView: View {

    @StateObject private var vm = ClipGeneratorViewModel()
    @StateObject private var featuresVm = FeaturesViewModel()
    @State private var selection: String? = "clip_creator"
    @State private var selectedGeneratedClipKey: String?
    @State private var selectedPostClipKey: String?
    @State private var inAppPreviewURL: URL?
    @State private var isInAppPreviewPresented = false

    var body: some View {
        NavigationSplitView {
            List(selection: $selection) {
                NavigationLink(value: "clip_creator") {
                    Label("Clip Creator", systemImage: "scissors")
                }
                NavigationLink(value: "generated") {
                    Label("Generated Clips", systemImage: "film")
                }
                NavigationLink(value: "post") {
                    Label("Post", systemImage: "paperplane")
                }
                NavigationLink(value: "features") {
                    Label("Features", systemImage: "star.fill")
                }
            }
            .navigationTitle("TikTok Upload Manager")
            .frame(minWidth: 220)
        } detail: {
            detailContent
                .frame(minWidth: 920, minHeight: 660)
        }
        .sheet(isPresented: $isInAppPreviewPresented, onDismiss: {
            inAppPreviewURL = nil
        }) {
            if let inAppPreviewURL {
                InAppClipPreviewSheet(videoURL: inAppPreviewURL)
            } else {
                Text("No clip selected for preview.")
                    .padding(24)
            }
        }
    }

    @ViewBuilder
    private var detailContent: some View {
        switch selection {
        case "generated":
            generatedClipsView
        case "post":
            postWorkspaceView
        case "features":
            featuresView
        default:
            clipCreatorView
        }
    }

    private var clipCreatorView: some View {
        ScrollView {
            VStack(spacing: 24) {
                header
                inputSection
                settingsSection
                actionSection

                if shouldShowProgressSection {
                    progressSection
                }

                generatedSection
            }
            .padding(32)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
    }

    private var generatedClipsView: some View {
        VStack(alignment: .leading, spacing: 24) {
            generatedHeader
            HStack(alignment: .top, spacing: 24) {
                generatedSection
                    .frame(width: 360, alignment: .topLeading)
                clipPreviewSection
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        }
        .padding(32)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .onAppear {
            syncSelectedClipAndPlayer()
        }
        .onChange(of: vm.generatedClips) {
            syncSelectedClipAndPlayer()
            syncPostSelection()
        }
    }

    private var postWorkspaceView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                postHeader
                postSummarySection

                HStack(alignment: .top, spacing: 20) {
                    postClipSelectionSection
                    postComposerSection
                }

                HStack(alignment: .top, spacing: 20) {
                    postQueueSection
                    updatesSection
                }

                postHistorySection
            }
            .padding(32)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .onAppear {
            syncPostSelection()
        }
        .onChange(of: vm.generatedClips) {
            syncPostSelection()
        }
        .onChange(of: selectedPostClipKey) {
            if vm.postCaptionDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                vm.applySuggestedCaption(for: selectedPostClip)
            }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("TikTok Upload Manager")
                .font(.largeTitle)
                .fontWeight(.semibold)

            Text("AI Clip Creator")
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var generatedHeader: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Generated Clips")
                    .font(.largeTitle)
                    .fontWeight(.semibold)

                Text("Review saved videos from SQLite with upload status.")
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Button("Refresh") {
                vm.refreshGeneratedClipsFromBackend()
            }
            .buttonStyle(.bordered)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var postHeader: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("Post")
                .font(.largeTitle)
                .fontWeight(.semibold)

            Text("Caption, queue, and posting workflow unified in the new UI.")
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var inputSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Video Source")
                .font(.headline)

            Picker("Source", selection: $vm.sourceMode) {
                ForEach(ClipGeneratorViewModel.SourceMode.allCases) { mode in
                    Text(mode.rawValue).tag(mode)
                }
            }
            .pickerStyle(.segmented)

            if vm.sourceMode != .aiVideo {
                HStack(spacing: 8) {
                    TextField("Paste video URL or file path", text: $vm.videoURL)
                        .textFieldStyle(.roundedBorder)

                    Button("Browse") {
                        vm.pickVideoFile()
                    }
                    .buttonStyle(.bordered)
                }
            } else {
                Text("AI will generate a complete video from scratch")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(.vertical, 8)
            }
        }
    }

    private var settingsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Settings")
                .font(.headline)

            if vm.sourceMode == .aiVideo {
                aiVideoSettingsSection
            } else {
                regularClipSettingsSection
            }
        }
    }

    private var aiVideoSettingsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Video Type")
                    .font(.subheadline)
                    .fontWeight(.medium)

                Picker("Video Type", selection: $vm.aiVideoType) {
                    ForEach(ClipGeneratorViewModel.AIVideoType.allCases) { type in
                        Text(type.title).tag(type)
                    }
                }
                .pickerStyle(.segmented)

                Text(vm.aiVideoType.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Theme")
                    .font(.subheadline)
                    .fontWeight(.medium)

                Picker("Theme", selection: $vm.aiVideoTheme) {
                    ForEach(ClipGeneratorViewModel.AIVideoTheme.allCases) { theme in
                        Text(theme.title).tag(theme)
                    }
                }
                .pickerStyle(.menu)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Duration")
                    .font(.subheadline)
                    .fontWeight(.medium)

                Picker("Duration", selection: $vm.aiVideoDuration) {
                    ForEach(ClipGeneratorViewModel.AIVideoDuration.allCases) { duration in
                        Text(duration.title).tag(duration)
                    }
                }
                .pickerStyle(.segmented)
            }

            Divider()

            VStack(alignment: .leading, spacing: 8) {
                Text("AI Video Features")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.blue)

                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                    Text("AI-generated script")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                    Text("Professional AI voiceover")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                    Text("Auto-generated captions")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                HStack(spacing: 4) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                    Text("Themed background video")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }

    private var regularClipSettingsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Clip Format")
                    .font(.subheadline)
                    .fontWeight(.medium)

                Picker("Clip Format", selection: $vm.clipFormat) {
                    ForEach(ClipGeneratorViewModel.ClipFormat.allCases) { format in
                        Text(format.title).tag(format)
                    }
                }
                .pickerStyle(.menu)

                Text(vm.clipFormat.details)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Content Theme")
                    .font(.subheadline)
                    .fontWeight(.medium)

                Picker("Content Theme", selection: $vm.contentTheme) {
                    ForEach(ClipGeneratorViewModel.ContentTheme.allCases) { theme in
                        Text(theme.title).tag(theme)
                    }
                }
                .pickerStyle(.menu)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Variation Mode")
                    .font(.subheadline)
                    .fontWeight(.medium)

                Picker("Variation Mode", selection: $vm.variationMode) {
                    ForEach(ClipGeneratorViewModel.VariationMode.allCases) { mode in
                        Text(mode.title).tag(mode)
                    }
                }
                .pickerStyle(.segmented)

                Text(vm.variationMode.details)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Divider()

            Stepper("Clip Duration: \(vm.clipDuration)s", value: $vm.clipDuration, in: 5...120)
            Stepper("Max Clips: \(vm.maxClips)", value: $vm.maxClips, in: 1...20)

            Toggle("Add AI Captions", isOn: $vm.addCaptions)
            Toggle("Add Background Music", isOn: $vm.addMusic)
            Toggle("Apply Visual Effects", isOn: $vm.applyEffects)

            Divider()

            VStack(alignment: .leading, spacing: 8) {
                Text("Enhanced Features")
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .foregroundColor(.blue)

                Toggle("Smart Backgrounds", isOn: $vm.useSmartBackgrounds)
                    .help("Use themed gameplay backgrounds (GTA, Minecraft, Subway Surfers)")

                if vm.useSmartBackgrounds {
                    HStack {
                        Text("Theme:")
                            .font(.caption)
                        Picker("", selection: $vm.backgroundTheme) {
                            Text("Scary").tag("scary")
                            Text("Dating").tag("dating")
                            Text("Crazy").tag("crazy")
                            Text("Motivational").tag("motivational")
                            Text("Mystery").tag("mystery")
                        }
                        .pickerStyle(.menu)
                        .frame(width: 140)
                    }
                    .padding(.leading)
                }

                Toggle("Auto-Track Posts", isOn: $vm.autoTrackPost)
                    .help("Automatically track generated clips to selected account")

                if vm.autoTrackPost {
                    HStack {
                        Text("Account:")
                            .font(.caption)
                        Picker("", selection: $vm.selectedAccountUsername) {
                            Text("Select Account...").tag("")
                            ForEach(featuresVm.accounts) { account in
                                Text("@\(account.username)").tag(account.username)
                            }
                        }
                        .pickerStyle(.menu)
                        .frame(width: 160)
                        .onAppear {
                            featuresVm.loadAccounts()
                        }
                    }
                    .padding(.leading)
                }
            }

            Divider()
            shortformEngineSection
        }
    }

    private var shortformEngineSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Shortform AI Engine")
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(.blue)

            Toggle("Enable Shortform AI Optimization", isOn: $vm.shortformAIEnabled)
                .help("Runs retention/aesthetic optimization after every render.")

            HStack(spacing: 8) {
                Circle()
                    .fill(shortformStatusColor)
                    .frame(width: 8, height: 8)
                Text(shortformStatusText)
                    .font(.caption)
                    .foregroundStyle(shortformStatusColor)
            }

            Stepper(
                "Aesthetic Threshold: \(vm.shortformAestheticThreshold)",
                value: $vm.shortformAestheticThreshold,
                in: 50...95
            )
            Stepper(
                "Engagement Threshold: \(vm.shortformEngagementThreshold)",
                value: $vm.shortformEngagementThreshold,
                in: 50...95
            )

            if let aesthetic = vm.shortformLastAestheticScore,
               let engagement = vm.shortformLastEngagementScore {
                Text("Last scores: Aesthetic \(aesthetic)/100 • Engagement \(engagement)/100 • Source: \(vm.shortformLastValidationSource)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            } else {
                Text("Run a clip to capture live shortform metrics.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if vm.shortformLastCorrections != "none" {
                Text("Corrections: \(vm.shortformLastCorrections)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
        }
    }

    private var actionSection: some View {
        HStack(spacing: 12) {
            Button(vm.sourceMode == .aiVideo ? "Generate AI Video" : "Generate Clips") {
                vm.generateClips()
            }
            .buttonStyle(.borderedProminent)
            .disabled(vm.isProcessing)

            if vm.isProcessing {
                Button("Stop") {
                    vm.stop()
                }
                .buttonStyle(.bordered)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                HStack(spacing: 6) {
                    Circle()
                        .fill(statusColor)
                        .frame(width: 8, height: 8)
                    Text(statusLabel)
                        .font(.caption)
                        .foregroundStyle(statusColor)
                }

                Text(vm.progressText)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
    }

    private var progressSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Run Output")
                    .font(.headline)

                Spacer()

                if !vm.logs.isEmpty {
                    Button("Clear Log") {
                        vm.logs = ""
                    }
                    .buttonStyle(.plain)
                }
            }

            if vm.runState == .failed {
                Text(vm.sourceMode == .aiVideo
                    ? "AI video generation failed. Inspect logs below for details."
                    : "Clip generation failed. Inspect logs below for details.")
                    .font(.subheadline)
                    .foregroundStyle(.red)
            }

            if let progress = vm.progressValue {
                ProgressView(value: progress)
            } else {
                ProgressView()
            }

            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        Text(vm.logs.isEmpty ? "No output yet..." : vm.logs)
                            .font(.system(.caption, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)

                        // Invisible anchor at the bottom for auto-scroll
                        Color.clear
                            .frame(height: 1)
                            .id("bottom")
                    }
                    .padding(6)
                }
                .frame(height: 160)
                .background(Color(NSColor.windowBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .onChange(of: vm.logs) { _ in
                    // Auto-scroll to bottom when logs update
                    withAnimation {
                        proxy.scrollTo("bottom", anchor: .bottom)
                    }
                }
                .onAppear {
                    // Scroll to bottom on initial load if there are logs
                    if !vm.logs.isEmpty {
                        proxy.scrollTo("bottom", anchor: .bottom)
                    }
                }
            }
        }
    }

    private var generatedSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Generated Clips")
                .font(.headline)

            if vm.generatedClips.isEmpty {
                Text("No clips generated yet.")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 160, alignment: .leading)
                    .padding(12)
                    .background(Color(NSColor.windowBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                List(vm.generatedClips, selection: $selectedGeneratedClipKey) { clip in
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Text(clip.fileName)
                            Spacer()
                            clipStatusBadge(clip)
                        }
                        Text("\(clip.duration)s • \(clip.size)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        if let uploadStatus = clip.uploadStatus, !uploadStatus.isEmpty {
                            Text("Upload: \(uploadStatus.capitalized) • Retries: \(clip.retryCount ?? 0)")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        if let path = clip.path, !path.isEmpty {
                            Text(path)
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                                .lineLimit(1)
                        }
                    }
                    .padding(.vertical, 2)
                    .tag(clipSelectionKey(for: clip))
                }
                .frame(minHeight: 220)
            }
        }
    }

    private var clipPreviewSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Preview")
                .font(.headline)

            if let clip = selectedGeneratedClip {
                if let path = clip.path, !path.isEmpty, FileManager.default.fileExists(atPath: path) {
                    VStack(alignment: .leading, spacing: 8) {
                        Image(systemName: "film.stack")
                            .font(.system(size: 34))
                            .foregroundStyle(.secondary)
                        Text("In-app preview is available.")
                            .font(.subheadline)
                        Text("Use Preview In App to watch here, or Open Clip for your default player.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 220, alignment: .topLeading)
                    .padding(12)
                    .background(Color(NSColor.windowBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 10))

                    HStack(spacing: 8) {
                        Button("Preview In App") {
                            openInAppPreview(clip)
                        }
                        .buttonStyle(.borderedProminent)

                        Button("Open Clip") {
                            vm.openClip(clip)
                        }
                        .buttonStyle(.bordered)

                        Button("Reveal in Finder") {
                            vm.revealClipInFinder(clip)
                        }
                        .buttonStyle(.bordered)

                        Button("Queue for Post") {
                            selectedPostClipKey = clipSelectionKey(for: clip)
                            vm.queueClipForPost(clip)
                        }
                        .buttonStyle(.bordered)

                        Button("Retry Upload") {
                            vm.retryClipUpload(clip)
                        }
                        .buttonStyle(.bordered)

                        Button("Delete") {
                            vm.deleteClip(clip)
                        }
                        .buttonStyle(.bordered)
                    }

                    Text(clip.fileName)
                        .font(.subheadline)
                        .fontWeight(.medium)
                } else {
                    Text("This clip can’t be previewed yet. Select a clip with a valid local file path.")
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 160, alignment: .topLeading)
                        .padding(12)
                        .background(Color(NSColor.windowBackgroundColor))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                }
            } else {
                Text("Select a generated clip, then press Play.")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 160, alignment: .topLeading)
                    .padding(12)
                    .background(Color(NSColor.windowBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var postSummarySection: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Last Generation")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(vm.lastRunSummary)
                    .font(.subheadline)
                    .lineLimit(2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(Color(NSColor.windowBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 8))

            VStack(alignment: .leading, spacing: 4) {
                Text("Post Status")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text(vm.postStatusText)
                    .font(.subheadline)
                    .lineLimit(2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
            .background(Color(NSColor.windowBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
    }

    private var postClipSelectionSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Choose Clip")
                .font(.headline)

            if vm.generatedClips.isEmpty {
                Text("Generate clips first, then pick one to post.")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 220, alignment: .topLeading)
                    .padding(12)
                    .background(Color(NSColor.windowBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                List(vm.generatedClips, selection: $selectedPostClipKey) { clip in
                    VStack(alignment: .leading, spacing: 2) {
                        HStack {
                            Text(clip.fileName)
                            Spacer()
                            clipStatusBadge(clip)
                        }
                        Text("\(clip.duration)s • \(clip.size)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .tag(clipSelectionKey(for: clip))
                }
                .frame(minWidth: 260, minHeight: 260)
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var postComposerSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Post Composer")
                .font(.headline)

            TextField("Hashtag set", text: $vm.postHashtags)
                .textFieldStyle(.roundedBorder)

            TextEditor(text: $vm.postCaptionDraft)
                .font(.body)
                .frame(minHeight: 180)
                .padding(6)
                .background(Color(NSColor.windowBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 8))

            Toggle("Schedule this post", isOn: $vm.schedulePost)
            if vm.schedulePost {
                DatePicker("Post time", selection: $vm.scheduledPostDate)
                    .datePickerStyle(.compact)
            }

            HStack(spacing: 8) {
                Button("Use Suggested") {
                    vm.applySuggestedCaption(for: selectedPostClip)
                }
                .buttonStyle(.bordered)

                Button("Copy Caption") {
                    vm.copyCaptionToClipboard()
                }
                .buttonStyle(.bordered)

                Button("Auto-Upload to TikTok") {
                    guard let clip = selectedPostClip else {
                        vm.postStatusText = "Select a clip first"
                        return
                    }

                    let videoPath = clip.path
                    let caption = vm.postCaptionDraft.trimmingCharacters(in: .whitespacesAndNewlines)
                    vm.openTikTokUploadPage(videoPath: videoPath, caption: caption)
                }
                .buttonStyle(.bordered)
                .disabled(selectedPostClip == nil)
            }

            HStack(spacing: 8) {
                Button("Open Clip") {
                    vm.openClip(selectedPostClip)
                }
                .buttonStyle(.bordered)

                Button("Reveal in Finder") {
                    vm.revealClipInFinder(selectedPostClip)
                }
                .buttonStyle(.bordered)

                Button("Add to Queue") {
                    vm.queueClipForPost(selectedPostClip)
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var postQueueSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Post Queue")
                .font(.headline)

            if vm.postQueue.isEmpty {
                Text("Queue is empty.")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 220, alignment: .topLeading)
                    .padding(12)
                    .background(Color(NSColor.windowBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(vm.postQueue) { item in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(item.clipFileName)
                                    .fontWeight(.medium)
                                if let scheduledAt = item.scheduledAt {
                                    Text("Scheduled: \(scheduledAt.formatted(date: .abbreviated, time: .shortened))")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                } else {
                                    Text("Queued: \(item.createdAt.formatted(date: .abbreviated, time: .shortened))")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                }

                                HStack(spacing: 8) {
                                    Button("Open") {
                                        vm.openQueueItemClip(item)
                                    }
                                    .buttonStyle(.bordered)

                                    Button("Post to TikTok") {
                                        let caption = item.caption.isEmpty ? nil : item.caption
                                        vm.openTikTokUploadPage(videoPath: item.clipPath, caption: caption)
                                    }
                                    .buttonStyle(.borderedProminent)

                                    Button("Mark Posted") {
                                        vm.markQueueItemPosted(item)
                                    }
                                    .buttonStyle(.bordered)

                                    Button("Remove") {
                                        vm.removeQueueItem(item)
                                    }
                                    .buttonStyle(.bordered)
                                }
                            }
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color(NSColor.windowBackgroundColor))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                    }
                }
                .frame(minHeight: 220)
            }
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var updatesSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Updates & News")
                .font(.headline)

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    ForEach(vm.updatesFeed.prefix(20)) { item in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.message)
                                .font(.subheadline)
                            Text(item.timestamp.formatted(date: .abbreviated, time: .shortened))
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(feedColor(for: item.level).opacity(0.12))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }
                }
            }
            .frame(minHeight: 220)
        }
        .frame(maxWidth: .infinity, alignment: .topLeading)
    }

    private var postHistorySection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Post History")
                .font(.headline)

            if vm.postHistory.isEmpty {
                Text("No history yet.")
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, minHeight: 120, alignment: .leading)
                    .padding(12)
                    .background(Color(NSColor.windowBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
            } else {
                List(vm.postHistory.prefix(25)) { item in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(item.clipFileName)
                        Text("\(item.outcome.rawValue.capitalized) • \(item.completedAt.formatted(date: .abbreviated, time: .shortened))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(item.notes)
                            .font(.caption2)
                            .foregroundStyle(.tertiary)
                    }
                }
                .frame(minHeight: 160)
            }
        }
    }

    private var selectedGeneratedClip: Clip? {
        guard let key = selectedGeneratedClipKey else { return nil }
        return vm.generatedClips.first(where: { clipSelectionKey(for: $0) == key })
    }

    private var selectedPostClip: Clip? {
        guard let key = selectedPostClipKey else { return nil }
        return vm.generatedClips.first(where: { clipSelectionKey(for: $0) == key })
    }

    private func clipSelectionKey(for clip: Clip) -> String {
        clip.path ?? clip.fileName
    }

    private func syncSelectedClipAndPlayer() {
        guard !vm.generatedClips.isEmpty else {
            selectedGeneratedClipKey = nil
            return
        }

        if let key = selectedGeneratedClipKey,
           vm.generatedClips.contains(where: { clipSelectionKey(for: $0) == key }) {
            return
        }

        selectedGeneratedClipKey = clipSelectionKey(for: vm.generatedClips[0])
    }

    private func syncPostSelection() {
        guard !vm.generatedClips.isEmpty else {
            selectedPostClipKey = nil
            return
        }

        if let key = selectedPostClipKey,
           vm.generatedClips.contains(where: { clipSelectionKey(for: $0) == key }) {
            return
        }

        selectedPostClipKey = clipSelectionKey(for: vm.generatedClips[0])
        if vm.postCaptionDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            vm.applySuggestedCaption(for: vm.generatedClips[0])
        }
    }

    private func openInAppPreview(_ clip: Clip) {
        guard let path = clip.path, !path.isEmpty else { return }
        let url = URL(fileURLWithPath: path)
        guard FileManager.default.fileExists(atPath: url.path) else { return }
        inAppPreviewURL = url
        isInAppPreviewPresented = true
    }

    private func feedColor(for level: ClipGeneratorViewModel.FeedLevel) -> Color {
        switch level {
        case .info:
            return .blue
        case .success:
            return .green
        case .warning:
            return .orange
        case .error:
            return .red
        }
    }

    private func clipStatusBadge(_ clip: Clip) -> some View {
        let statusText = (clip.uploadStatus ?? clip.status).capitalized
        return Text(statusText)
            .font(.caption2)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(clipStatusColor(clip).opacity(0.2))
            .clipShape(Capsule())
    }

    private func clipStatusColor(_ clip: Clip) -> Color {
        let status = (clip.uploadStatus ?? clip.status).lowercased()
        switch status {
        case "posted", "success":
            return .green
        case "uploading":
            return .blue
        case "failed":
            return .red
        case "ready", "queued":
            return .orange
        default:
            return .secondary
        }
    }

    private var shouldShowProgressSection: Bool {
        vm.isProcessing
            || !vm.logs.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || vm.runState != .idle
    }

    private var statusLabel: String {
        switch vm.runState {
        case .idle:
            return "Idle"
        case .running:
            return "Running"
        case .succeeded:
            return "Success"
        case .failed:
            return "Failed"
        case .stopped:
            return "Stopped"
        }
    }

    private var statusColor: Color {
        switch vm.runState {
        case .idle:
            return .secondary
        case .running:
            return .blue
        case .succeeded:
            return .green
        case .failed:
            return .red
        case .stopped:
            return .orange
        }
    }

    private var shortformStatusText: String {
        if !vm.shortformAIEnabled {
            return "Disabled"
        }
        if vm.shortformDetectedThisRun {
            return "Integrated: Active in latest run"
        }
        return "Enabled: waiting for next render"
    }

    private var shortformStatusColor: Color {
        if !vm.shortformAIEnabled {
            return .secondary
        }
        if vm.shortformDetectedThisRun {
            return .green
        }
        return .orange
    }

    // MARK: - Features View

    private var featuresView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                featuresHeader
                tiktokConnectionSection

                if let error = featuresVm.errorMessage {
                    errorBanner(error)
                }

                if !featuresVm.statusMessage.isEmpty {
                    statusBanner(featuresVm.statusMessage)
                }

                HStack(alignment: .top, spacing: 24) {
                    VStack(spacing: 24) {
                        accountsSection
                        analyticsSection
                    }
                    .frame(width: 440)

                    backgroundsSection
                }
            }
            .padding(32)
        }
        .onAppear {
            // Auto-load everything when Features tab appears
            if featuresVm.accounts.isEmpty {
                featuresVm.loadAccounts()
            }
            if featuresVm.backgrounds.isEmpty {
                featuresVm.loadBackgrounds()
            }
            if featuresVm.analytics == nil {
                featuresVm.loadAnalytics()
            }
            featuresVm.refreshTikTokAuthStatus()
        }
    }

    private var featuresHeader: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Features")
                .font(.largeTitle)
                .fontWeight(.bold)

            Text("Manage OAuth connection, accounts, backgrounds, and analytics")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    private var tiktokConnectionSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("TikTok Connection", systemImage: "link")
                    .font(.headline)
                Spacer()
                Circle()
                    .fill(featuresVm.authStatus.connected ? Color.green : Color.red)
                    .frame(width: 10, height: 10)
                Text(featuresVm.authStatus.connected ? "Connected" : "Not Connected")
                    .font(.subheadline)
                    .foregroundColor(featuresVm.authStatus.connected ? .green : .red)
            }

            HStack {
                Text("Token expires in:")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Text(featuresVm.authCountdownLabel())
                    .font(.system(.subheadline, design: .monospaced))
            }

            HStack(spacing: 8) {
                Button("Connect TikTok") {
                    featuresVm.connectTikTok()
                }
                .buttonStyle(.borderedProminent)

                Button("Refresh Status") {
                    featuresVm.refreshTikTokAuthStatus()
                }
                .buttonStyle(.bordered)
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(12)
    }

    private func errorBanner(_ message: String) -> some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.red)
            Text(message)
                .font(.subheadline)
            Spacer()
            Button("Dismiss") {
                featuresVm.clearError()
            }
        }
        .padding()
        .background(Color.red.opacity(0.1))
        .cornerRadius(8)
    }

    private func statusBanner(_ message: String) -> some View {
        HStack {
            if featuresVm.isLoading {
                ProgressView()
                    .scaleEffect(0.8)
            } else {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.green)
            }
            Text(message)
                .font(.subheadline)
        }
        .padding()
        .background(Color.blue.opacity(0.1))
        .cornerRadius(8)
    }

    // MARK: - Accounts Section

    private var accountsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Accounts", systemImage: "person.2.fill")
                    .font(.headline)
                Spacer()
                Button(action: { featuresVm.loadAccounts() }) {
                    Image(systemName: "arrow.clockwise")
                }
                Button("Add Account") {
                    showAddAccountDialog()
                }
                .buttonStyle(.borderedProminent)
            }

            if featuresVm.accounts.isEmpty {
                emptyAccountsPlaceholder
            } else {
                accountsList
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(12)
    }

    private var emptyAccountsPlaceholder: some View {
        VStack(spacing: 12) {
            Image(systemName: "person.crop.circle.badge.plus")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("No accounts yet")
                .font(.headline)
            Text("Add your first account to start tracking")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
    }

    private var accountsList: some View {
        ForEach(featuresVm.accounts) { account in
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text("@\(account.username)")
                        .font(.headline)
                    Spacer()
                    Text(account.status)
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(statusColorForAccount(account.status))
                        .cornerRadius(4)
                }

                HStack {
                    Text(account.niche)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text("\(account.followers) followers")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if account.totalPosts > 0 {
                    HStack(spacing: 12) {
                        Label("\(account.totalViews)", systemImage: "eye.fill")
                        Label("\(account.totalLikes)", systemImage: "heart.fill")
                        Label("\(account.totalPosts)", systemImage: "film.fill")
                    }
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                }
            }
            .padding()
            .background(Color(nsColor: .windowBackgroundColor))
            .cornerRadius(8)
        }
    }

    private func statusColorForAccount(_ status: String) -> Color {
        switch status.lowercased() {
        case "active": return .green.opacity(0.2)
        case "created": return .blue.opacity(0.2)
        case "aging": return .yellow.opacity(0.2)
        case "banned": return .red.opacity(0.2)
        default: return .gray.opacity(0.2)
        }
    }

    private func showAddAccountDialog() {
        // FIXED: Use proper SwiftUI sheet instead of NSAlert for better UX
        let alert = NSAlert()
        alert.messageText = "Add TikTok Account"
        alert.informativeText = "Enter account details below:"
        alert.alertStyle = .informational

        // Create container view with proper frame
        let containerView = NSView(frame: NSRect(x: 0, y: 0, width: 320, height: 140))

        let stackView = NSStackView()
        stackView.orientation = .vertical
        stackView.spacing = 10
        stackView.alignment = .leading
        stackView.translatesAutoresizingMaskIntoConstraints = false

        // Username field
        let usernameLabel = NSTextField(labelWithString: "Username (without @):")
        let usernameField = NSTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24))
        usernameField.placeholderString = "my_tiktok_account"
        usernameField.isEditable = true
        usernameField.isSelectable = true
        usernameField.isBordered = true
        usernameField.isBezeled = true
        usernameField.bezelStyle = .roundedBezel
        usernameField.translatesAutoresizingMaskIntoConstraints = false
        usernameField.widthAnchor.constraint(equalToConstant: 300).isActive = true

        // Niche field
        let nicheLabel = NSTextField(labelWithString: "Niche:")
        let nicheField = NSTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24))
        nicheField.placeholderString = "horror, dating, crazy, motivational, etc."
        nicheField.isEditable = true
        nicheField.isSelectable = true
        nicheField.isBordered = true
        nicheField.isBezeled = true
        nicheField.bezelStyle = .roundedBezel
        nicheField.translatesAutoresizingMaskIntoConstraints = false
        nicheField.widthAnchor.constraint(equalToConstant: 300).isActive = true

        // Display name field
        let nameLabel = NSTextField(labelWithString: "Display Name (optional):")
        let nameField = NSTextField(frame: NSRect(x: 0, y: 0, width: 300, height: 24))
        nameField.placeholderString = "My TikTok Page"
        nameField.isEditable = true
        nameField.isSelectable = true
        nameField.isBordered = true
        nameField.isBezeled = true
        nameField.bezelStyle = .roundedBezel
        nameField.translatesAutoresizingMaskIntoConstraints = false
        nameField.widthAnchor.constraint(equalToConstant: 300).isActive = true

        stackView.addArrangedSubview(usernameLabel)
        stackView.addArrangedSubview(usernameField)
        stackView.addArrangedSubview(nicheLabel)
        stackView.addArrangedSubview(nicheField)
        stackView.addArrangedSubview(nameLabel)
        stackView.addArrangedSubview(nameField)

        containerView.addSubview(stackView)

        // Add constraints
        NSLayoutConstraint.activate([
            stackView.leadingAnchor.constraint(equalTo: containerView.leadingAnchor, constant: 10),
            stackView.trailingAnchor.constraint(equalTo: containerView.trailingAnchor, constant: -10),
            stackView.topAnchor.constraint(equalTo: containerView.topAnchor, constant: 10),
            stackView.bottomAnchor.constraint(equalTo: containerView.bottomAnchor, constant: -10)
        ])

        alert.accessoryView = containerView
        alert.addButton(withTitle: "Add Account")
        alert.addButton(withTitle: "Cancel")

        let response = alert.runModal()

        if response == .alertFirstButtonReturn {
            let username = usernameField.stringValue.trimmingCharacters(in: .whitespaces)
            let niche = nicheField.stringValue.trimmingCharacters(in: .whitespaces)
            let name = nameField.stringValue.trimmingCharacters(in: .whitespaces)

            if username.isEmpty {
                let errorAlert = NSAlert()
                errorAlert.messageText = "Username Required"
                errorAlert.informativeText = "Please enter a username for the account."
                errorAlert.alertStyle = .warning
                errorAlert.runModal()
                return
            }

            if niche.isEmpty {
                let errorAlert = NSAlert()
                errorAlert.messageText = "Niche Required"
                errorAlert.informativeText = "Please enter a niche (e.g., horror, dating, crazy)."
                errorAlert.alertStyle = .warning
                errorAlert.runModal()
                return
            }

            featuresVm.addAccount(
                username: username,
                niche: niche,
                name: name.isEmpty ? username : name
            )
        }
    }

    // MARK: - Analytics Section

    private var analyticsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Analytics", systemImage: "chart.bar.fill")
                    .font(.headline)
                Spacer()
                Button(action: { featuresVm.loadAnalytics() }) {
                    Image(systemName: "arrow.clockwise")
                }
            }

            if let analytics = featuresVm.analytics {
                VStack(spacing: 8) {
                    analyticsRow(label: "Total Views", value: "\(analytics.totalViews)", icon: "eye.fill")
                    analyticsRow(label: "Total Likes", value: "\(analytics.totalLikes)", icon: "heart.fill")
                    analyticsRow(label: "Total Posts", value: "\(analytics.totalPosts)", icon: "film.fill")

                    if let accounts = analytics.activeAccounts {
                        analyticsRow(label: "Active Accounts", value: "\(accounts)", icon: "person.2.fill")
                    }
                }
            } else {
                Button("Load Analytics") {
                    featuresVm.loadAnalytics()
                }
                .frame(maxWidth: .infinity)
                .padding()
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(12)
    }

    private func analyticsRow(label: String, value: String, icon: String) -> some View {
        HStack {
            Label(label, systemImage: icon)
                .font(.subheadline)
            Spacer()
            Text(value)
                .font(.headline)
                .foregroundColor(.blue)
        }
        .padding(.vertical, 4)
    }

    // MARK: - Backgrounds Section

    private var backgroundsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Background Videos", systemImage: "photo.fill")
                    .font(.headline)
                Spacer()
                Button(action: { featuresVm.loadBackgrounds() }) {
                    Image(systemName: "arrow.clockwise")
                }
                Button("Download") {
                    featuresVm.downloadBackgrounds()
                }
                .buttonStyle(.borderedProminent)
            }

            if featuresVm.backgrounds.isEmpty {
                emptyBackgroundsPlaceholder
            } else {
                backgroundsList
            }
        }
        .padding()
        .background(Color(nsColor: .controlBackgroundColor))
        .cornerRadius(12)
    }

    private var emptyBackgroundsPlaceholder: some View {
        VStack(spacing: 12) {
            Image(systemName: "video.badge.plus")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("No backgrounds yet")
                .font(.headline)
            Text("Download gameplay backgrounds from YouTube")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 32)
    }

    private var backgroundsList: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 4) {
                ForEach(featuresVm.backgrounds) { background in
                    HStack {
                        Image(systemName: "video.fill")
                            .foregroundColor(.blue)
                        Text(background.name)
                            .font(.caption)
                            .lineLimit(1)
                        Spacer()
                        if let theme = background.theme {
                            Text(theme)
                                .font(.caption2)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.blue.opacity(0.2))
                                .cornerRadius(4)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
        .frame(height: 300)
    }
}

private struct InAppClipPreviewSheet: View {
    let videoURL: URL
    @State private var player = AVPlayer()

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(videoURL.lastPathComponent)
                .font(.headline)
                .lineLimit(1)

            VideoPlayer(player: player)
                .frame(minWidth: 900, minHeight: 560)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .onAppear {
                    let item = AVPlayerItem(url: videoURL)
                    player.replaceCurrentItem(with: item)
                    player.play()
                }
                .onDisappear {
                    player.pause()
                    player.replaceCurrentItem(with: nil)
                }
        }
        .padding(20)
    }
}
