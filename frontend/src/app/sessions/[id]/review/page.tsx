"use client";

import { use, useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  configureSession,
  startExecution,
  checkBrowsers,
  uploadTestFiles,
} from "@/lib/api";
import { useSessionStore } from "@/lib/store";

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: sessionId } = use(params);
  const router = useRouter();
  const store = useSessionStore();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [customName, setCustomName] = useState("");
  const [customPath, setCustomPath] = useState("");
  const [browserStatus, setBrowserStatus] = useState<
    Record<string, { available: boolean; message: string }>
  >({});
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const {
    sections,
    selectedSections,
    selectedTestIds,
    executionMode,
    concurrency,
    model,
    systemPrompt,
    testConfig,
    documentTitle,
  } = store;

  const allTestCases = sections.flatMap((s) => s.test_cases);
  const selectedCount = selectedTestIds.length;

  const totalBrowsers = store.browsers.length + store.customBrowsers.length;

  const handleCheckBrowsers = async () => {
    try {
      const res = await checkBrowsers(
        store.browsers,
        store.customBrowsers
      );
      const statusMap: Record<string, { available: boolean; message: string }> = {};
      for (const r of res.results) {
        statusMap[r.name] = { available: r.available, message: r.message };
      }
      setBrowserStatus(statusMap);
    } catch {
      // silently fail
    }
  };

  const handleFileUpload = useCallback(
    async (files: FileList | File[]) => {
      const fileArray = Array.from(files);
      if (fileArray.length === 0) return;
      setUploading(true);
      try {
        const res = await uploadTestFiles(sessionId, fileArray);
        store.addUploadedTestFiles(res.filenames);
        store.setUploadFolder(res.upload_folder);
      } catch (e: any) {
        setError(e.message || "Failed to upload files");
      } finally {
        setUploading(false);
      }
    },
    [sessionId, store]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      if (e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files);
      }
    },
    [handleFileUpload]
  );

  const handleAddCustomBrowser = () => {
    if (customName.trim() && customPath.trim()) {
      store.addCustomBrowser({
        name: customName.trim(),
        executable_path: customPath.trim(),
      });
      setCustomName("");
      setCustomPath("");
    }
  };

  const handleRun = async () => {
    setLoading(true);
    setError("");
    try {
      await configureSession(sessionId, {
        selected_sections: selectedSections,
        selected_test_ids: selectedTestIds,
        execution_mode: executionMode,
        concurrency,
        model,
        browsers: store.browsers,
        custom_browsers: store.customBrowsers,
        system_prompt: systemPrompt,
        upload_folder: store.uploadFolder || null,
        max_retries: 0,
      });

      await startExecution(sessionId);
      store.setExecutionStatus("running");
      router.push(`/sessions/${sessionId}/execute`);
    } catch (e: any) {
      setError(e.message || "Failed to start execution");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Review & Configure</h1>
            {documentTitle && (
              <p className="text-muted-foreground">{documentTitle}</p>
            )}
          </div>
          <Button variant="outline" onClick={() => router.push("/")}>
            Back
          </Button>
        </div>

        {/* Configuration Panel */}
        <Card>
          <CardHeader>
            <CardTitle>Execution Configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              {/* Execution Mode */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Execution Mode</label>
                <RadioGroup
                  value={executionMode}
                  onValueChange={(v) =>
                    store.setExecutionMode(v as "parallel" | "sequential")
                  }
                  className="flex gap-4"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="sequential" id="seq" />
                    <label htmlFor="seq" className="text-sm">Sequential</label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="parallel" id="par" />
                    <label htmlFor="par" className="text-sm">Parallel</label>
                  </div>
                </RadioGroup>
              </div>

              {/* Concurrency */}
              {executionMode === "parallel" && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Concurrency</label>
                  <Select
                    value={String(concurrency)}
                    onValueChange={(v) => store.setConcurrency(Number(v))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {[1, 2, 3, 5, 10].map((n) => (
                        <SelectItem key={n} value={String(n)}>
                          {n} parallel
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {/* Model */}
              <div className="space-y-2">
                <label className="text-sm font-medium">Model</label>
                <Select value={model} onValueChange={(v) => v && store.setModel(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gpt-4o">GPT-4o</SelectItem>
                    <SelectItem value="gpt-4o-mini">GPT-4o Mini</SelectItem>
                    <SelectItem value="claude-sonnet-4-20250514">Claude Sonnet 4</SelectItem>
                    <SelectItem value="claude-opus-4-20250514">Claude Opus 4</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Browser Selection */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium">
                  Browsers (tests run on each selected browser)
                </label>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleCheckBrowsers}
                >
                  Check Availability
                </Button>
              </div>
              <div className="flex flex-wrap gap-4">
                {[
                  { value: "chromium", label: "Chromium" },
                  { value: "firefox", label: "Firefox" },
                  { value: "webkit", label: "WebKit (Safari)" },
                  { value: "chrome", label: "Google Chrome" },
                  { value: "msedge", label: "Microsoft Edge" },
                ].map((b) => (
                  <div key={b.value} className="flex items-center space-x-2">
                    <Checkbox
                      id={`browser-${b.value}`}
                      checked={store.browsers.includes(b.value)}
                      onCheckedChange={() => store.toggleBrowser(b.value)}
                    />
                    <label htmlFor={`browser-${b.value}`} className="text-sm">
                      {b.label}
                    </label>
                    {browserStatus[b.value] && (
                      <span
                        className={`text-xs ${
                          browserStatus[b.value].available
                            ? "text-green-600"
                            : "text-red-500"
                        }`}
                      >
                        {browserStatus[b.value].available ? "(available)" : "(not found)"}
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {/* Custom Browsers */}
              {store.customBrowsers.length > 0 && (
                <div className="space-y-2">
                  <label className="text-xs font-medium text-muted-foreground">
                    Custom Browsers
                  </label>
                  {store.customBrowsers.map((cb) => (
                    <div
                      key={cb.name}
                      className="flex items-center gap-2 bg-muted p-2 rounded text-sm"
                    >
                      <Badge variant="outline">{cb.name}</Badge>
                      <span className="text-xs text-muted-foreground truncate flex-1">
                        {cb.executable_path}
                      </span>
                      {browserStatus[cb.name] && (
                        <span
                          className={`text-xs ${
                            browserStatus[cb.name].available
                              ? "text-green-600"
                              : "text-red-500"
                          }`}
                        >
                          {browserStatus[cb.name].available
                            ? "available"
                            : "not found"}
                        </span>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0"
                        onClick={() => store.removeCustomBrowser(cb.name)}
                      >
                        x
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {/* Add Custom Browser */}
              <div className="flex gap-2 items-end">
                <div className="space-y-1">
                  <label className="text-xs text-muted-foreground">
                    Browser Name
                  </label>
                  <Input
                    placeholder="e.g. Brave"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    className="h-8 text-sm w-32"
                  />
                </div>
                <div className="space-y-1 flex-1">
                  <label className="text-xs text-muted-foreground">
                    Executable Path
                  </label>
                  <Input
                    placeholder="e.g. C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
                    value={customPath}
                    onChange={(e) => setCustomPath(e.target.value)}
                    className="h-8 text-sm"
                  />
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8"
                  onClick={handleAddCustomBrowser}
                  disabled={!customName.trim() || !customPath.trim()}
                >
                  Add
                </Button>
              </div>

              {totalBrowsers > 1 && (
                <p className="text-xs text-muted-foreground">
                  {selectedCount * totalBrowsers} total test runs ({selectedCount} tests x {totalBrowsers} browsers)
                </p>
              )}
            </div>

            {/* Global config display */}
            {testConfig && (
              <div className="bg-muted p-3 rounded-md text-sm space-y-1">
                <p>
                  <span className="font-medium">App URL:</span>{" "}
                  {testConfig.app_url || "(not set)"}
                </p>
                {testConfig.credentials?.username && (
                  <p>
                    <span className="font-medium">Credentials:</span>{" "}
                    {testConfig.credentials.username} / ********
                  </p>
                )}
              </div>
            )}

            {/* System prompt */}
            <div className="space-y-2">
              <label className="text-sm font-medium">
                System Prompt (optional)
              </label>
              <Textarea
                placeholder="Custom instructions for the agent..."
                value={systemPrompt}
                onChange={(e) => store.setSystemPrompt(e.target.value)}
                rows={3}
              />
            </div>

            {/* Test Files Upload */}
            <div className="space-y-2">
              <label className="text-sm font-medium">
                Test Files (optional)
              </label>
              <p className="text-xs text-muted-foreground">
                Upload files the agent may need during test execution (e.g., images, documents, CSVs for file-upload test steps).
              </p>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`
                  border-2 border-dashed rounded-lg p-6 text-center cursor-pointer
                  transition-colors
                  ${dragging
                    ? "border-primary bg-primary/5"
                    : "border-muted-foreground/25 hover:border-muted-foreground/50"
                  }
                `}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files) {
                      handleFileUpload(e.target.files);
                      e.target.value = "";
                    }
                  }}
                />
                {uploading ? (
                  <p className="text-sm text-muted-foreground">Uploading...</p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Drag & drop files here, or click to browse
                  </p>
                )}
              </div>
              {store.uploadedTestFiles.length > 0 && (
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      {store.uploadedTestFiles.length} file{store.uploadedTestFiles.length !== 1 ? "s" : ""} uploaded
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs"
                      onClick={() => store.clearUploadedTestFiles()}
                    >
                      Clear
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {store.uploadedTestFiles.map((f) => (
                      <Badge key={f} variant="secondary" className="text-xs">
                        {f}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Test Cases */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">
              Test Cases ({selectedCount} of {allTestCases.length} selected)
            </h2>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => store.selectAllTestCases()}>
                Select All
              </Button>
              <Button variant="outline" size="sm" onClick={() => store.deselectAllTestCases()}>
                Deselect All
              </Button>
            </div>
          </div>

          <ScrollArea className="h-[500px] rounded-md border p-4">
            <div className="space-y-3">
              {sections.map((section) => (
                <div key={section.name}>
                  <h3 className="text-sm font-semibold text-muted-foreground mb-2">
                    {section.name} ({section.test_cases.length})
                  </h3>
                  {section.test_cases.map((tc) => (
                    <Card key={tc.id} className="mb-3">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <Checkbox
                            checked={selectedTestIds.includes(tc.id)}
                            onCheckedChange={() => store.toggleTestCase(tc.id)}
                            className="mt-1"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge variant="outline" className="text-xs">
                                {tc.id}
                              </Badge>
                              <span className="font-medium text-sm">
                                {tc.title}
                              </span>
                            </div>
                            {tc.steps.length > 0 && (
                              <ol className="text-sm text-muted-foreground list-decimal list-inside space-y-0.5">
                                {tc.steps.map((step, i) => (
                                  <li key={i}>{step}</li>
                                ))}
                              </ol>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                  <Separator className="my-3" />
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex justify-end">
          <Button
            size="lg"
            onClick={handleRun}
            disabled={selectedCount === 0 || loading}
          >
            {loading
              ? "Starting..."
              : totalBrowsers > 1
                ? `Run ${selectedCount} Tests on ${totalBrowsers} Browsers`
                : `Run ${selectedCount} Tests`}
          </Button>
        </div>
      </div>
    </div>
  );
}
