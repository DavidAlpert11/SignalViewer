classdef PlotManager < handle
    properties
        App
        PlotTabs
        AxesArrays
        AssignedSignals
        TabLayouts
        LinkedAxes
        SelectedSubplotIdx
        CurrentTabIdx
        LastSignalUpdateTimes
        GridLayouts
        TabControls
        MainTabGridLayouts
        % Add properties for stable streaming
        AxesLimits  % Store current limits to prevent jumping
        LastDataTime % Track last data time for each axes
        XAxisSignals
        TabSwitchTimer % Timer for smooth tab switching
        TabLinkedAxes % Per-tab axis linking state (logical array)
        TabLinkedAxesObjects % Per-tab linked axes objects (cell array)
        LastAddedCount
    end

    methods
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
        % PlotManager Methods
        %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

        % Constructor
        function obj = PlotManager(app)
            % Create a PlotManager for the given app
            obj.App = app;
            obj.PlotTabs = {};
            obj.AxesArrays = {};
            obj.AssignedSignals = {};
            obj.TabLayouts = {};
            obj.GridLayouts = {};
            obj.TabControls = {};
            obj.MainTabGridLayouts = {};
            obj.LinkedAxes = matlab.graphics.axis.Axes.empty;
            obj.CurrentTabIdx = 1;
            obj.SelectedSubplotIdx = 1;
            obj.AxesLimits = {};  % Initialize limits tracking
            obj.LastDataTime = {};  % Initialize time tracking
            obj.TabSwitchTimer = [];  % Initialize tab switch timer
            obj.TabLinkedAxes = [];  % Initialize per-tab linking states
            obj.TabLinkedAxesObjects = {};  % Initialize per-tab linked axes
        end

        % Initialize the plot manager (create the first tab)
        function initialize(obj)
            obj.createFirstTab();
            obj.setupTabCallbacks();
        end

        function createFirstTab(obj)
            % Create first tab with LIGHT MODE styling - NO X icon initially
            tab = uitab(obj.App.MainTabGroup, 'Title', 'Tab 1', ...
                'BackgroundColor', [0.98 0.98 0.98]);
            % Create a parent layout with 2 rows: [control panel; plot area]
            mainLayout = uigridlayout(tab, [2, 1]);
            mainLayout.RowHeight = {60, '1x'}; % Top row: fixed 60px, Bottom: fills remaining space
            mainLayout.ColumnWidth = {'1x'}; % Single column fills width

            % Initialize all arrays for the first tab
            obj.PlotTabs{1} = tab;
            obj.GridLayouts{1} = [];  % Will be assigned in createSubplotsForTab
            obj.AxesArrays{1} = matlab.ui.control.UIAxes.empty;
            obj.TabLayouts{1} = [2, 1];
            obj.AxesLimits{1} = {};
            obj.LastDataTime{1} = {};
            obj.TabControls{1} = [];

            % Store the main layout for this tab
            if ~isprop(obj, 'MainTabGridLayouts')
                obj.MainTabGridLayouts = {};
            end
            obj.MainTabGridLayouts{1} = mainLayout;

            % Initialize assigned signals for the first tab
            obj.AssignedSignals{1} = cell(2, 1);
            for i = 1:2
                obj.AssignedSignals{1}{i} = {};
            end

            % Initialize per-tab linking state
            obj.TabLinkedAxes(1) = false;  % First tab starts unlinked
            obj.TabLinkedAxesObjects{1} = [];

            % ADD CONTROLS FIRST (they go in row 1)
            obj.addTabControls(1);

            % THEN CREATE SUBPLOTS (they go in row 2)
            obj.createSubplotsForTab(1, 2, 1);

            obj.CurrentTabIdx = 1;

            % Highlight the first subplot
            obj.App.highlightSelectedSubplot(1, 1);

            % Ensure the + tab exists at the end
            obj.ensurePlusTab();
            obj.ensurePlusTabAtEnd();

            % Update tab titles to show/hide X icons appropriately
            obj.updateTabTitles();
        end
        function exportSubplotToFigure(obj, tabIdx, subplotIdx)
            % Export a specific subplot to a new MATLAB figure
            try
                if tabIdx > numel(obj.AxesArrays) || subplotIdx > numel(obj.AxesArrays{tabIdx})
                    return;
                end

                sourceAx = obj.AxesArrays{tabIdx}(subplotIdx);
                if ~isvalid(sourceAx)
                    return;
                end

                % Create new figure
                newFig = figure('Name', sprintf('Tab %d - Plot %d', tabIdx, subplotIdx), ...
                    'Position', [100 100 800 600], ...
                    'Color', [1 1 1]);



                % Create axes in the new figure
                newAx = axes(newFig);

                % Copy all children from source to new axes
                allChildren = allchild(sourceAx);
                validChildren = [];
                legendEntries = {};

                % Filter children: only copy actual signal plots (lines with DisplayName)
                for i = 1:numel(allChildren)
                    child = allChildren(i);

                    % Only copy line objects that represent actual signals
                    if isa(child, 'matlab.graphics.chart.primitive.Line') && ...
                            isprop(child, 'DisplayName') && ...
                            ~isempty(child.DisplayName) && ...
                            ~strcmp(child.DisplayName, '')

                        validChildren = [validChildren; child];
                        legendEntries{end+1} = child.DisplayName;
                    end
                end

                % Copy only the valid signal plots
                if ~isempty(validChildren)
                    copyobj(validChildren, newAx);
                end

                % Copy axes properties
                newAx.XLabel.String = sourceAx.XLabel.String;
                newAx.YLabel.String = sourceAx.YLabel.String;
                newAx.Title.String = sprintf('Tab %d - Plot %d', tabIdx, subplotIdx);
                % newAx.XLim = sourceAx.XLim;
                % newAx.YLim = sourceAx.YLim;

                % Copy grid settings
                grid(newAx, 'on');
                newAx.XGrid = sourceAx.XGrid;
                newAx.YGrid = sourceAx.YGrid;
                newAx.XMinorGrid = sourceAx.XMinorGrid;
                newAx.YMinorGrid = sourceAx.YMinorGrid;
                newAx.GridAlpha = sourceAx.GridAlpha;
                newAx.MinorGridAlpha = sourceAx.MinorGridAlpha;

                % ALWAYS use normal axes colors in export (not green highlight)
                newAx.XColor = [0.15 0.15 0.15];
                newAx.YColor = [0.15 0.15 0.15];
                newAx.LineWidth = 1;

                % Add legend only if we have valid entries
                if ~isempty(legendEntries)
                    legend(newAx, legendEntries, 'Location', 'best');
                end

                % Update status
                obj.App.StatusLabel.Text = sprintf('📊 Exported Plot %d to MATLAB Figure', subplotIdx);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = ['Export failed: ' ME.message];
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
            obj.App.restoreFocus(); % Restore focus after context menu action

        end
        function copySubplotToClipboard(obj, tabIdx, subplotIdx)
            % Copy subplot to clipboard as image
            try
                if tabIdx > numel(obj.AxesArrays) || subplotIdx > numel(obj.AxesArrays{tabIdx})
                    return;
                end

                sourceAx = obj.AxesArrays{tabIdx}(subplotIdx);
                if ~isvalid(sourceAx)
                    return;
                end

                % Create temporary figure for export
                tempFig = figure('Visible', 'off', 'Position', [0 0 800 600]);
                tempAx = axes(tempFig);

                % Copy content excluding highlight borders
                allChildren = allchild(sourceAx);
                validChildren = [];

                % Filter out highlight border lines
                highlightBorders = [];
                if isstruct(sourceAx.UserData) && isfield(sourceAx.UserData, 'HighlightBorders')
                    highlightBorders = sourceAx.UserData.HighlightBorders;
                end

                for i = 1:numel(allChildren)
                    child = allChildren(i);
                    % Only copy if it's not a highlight border
                    if ~any(highlightBorders == child)
                        validChildren = [validChildren; child];
                    end
                end

                % Copy only the valid children
                if ~isempty(validChildren)
                    copyobj(validChildren, tempAx);
                end

                tempAx.XLabel.String = sourceAx.XLabel.String;
                tempAx.YLabel.String = sourceAx.YLabel.String;
                tempAx.Title.String = sprintf('Tab %d - Plot %d', tabIdx, subplotIdx);
                % tempAx.XLim = sourceAx.XLim;
                % tempAx.YLim = sourceAx.YLim;

                % Set normal colors
                tempAx.XColor = [0.15 0.15 0.15];
                tempAx.YColor = [0.15 0.15 0.15];
                tempAx.LineWidth = 1;

                % Copy to clipboard
                print(tempFig, '-dbitmap');

                % Clean up
                close(tempFig);

                obj.App.StatusLabel.Text = sprintf('📋 Plot %d copied to clipboard', subplotIdx);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = ['❌ Copy failed: ' ME.message];
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];            end
        end

        function enhancedCsvLabel = generateEnhancedCSVLabel(obj, csvIdx)
            if csvIdx == -1
                enhancedCsvLabel = 'derived';
                return;
            end

            csvPath = obj.App.DataManager.CSVFilePaths{csvIdx};
            [csvDir, csvName, csvExt] = fileparts(csvPath);
            [~, folderName] = fileparts(csvDir);  % Get parent folder name

            % Check if there are other CSVs with the same filename
            currentFileName = [csvName csvExt];
            hasConflict = false;

            for k = 1:numel(obj.App.DataManager.CSVFilePaths)
                if k == csvIdx, continue; end  % Skip self
                [~, otherName, otherExt] = fileparts(obj.App.DataManager.CSVFilePaths{k});
                if strcmp([otherName otherExt], currentFileName)
                    hasConflict = true;
                    break;
                end
            end

            if hasConflict
                % Multiple CSVs have same filename - include folder name
                enhancedCsvLabel = [folderName '_' csvName];
            else
                % Unique filename - use just the CSV name
                enhancedCsvLabel = csvName;
            end
        end
        function saveSubplotAsImage(obj, tabIdx, subplotIdx)
            % Save subplot as image file
            try
                if tabIdx > numel(obj.AxesArrays) || subplotIdx > numel(obj.AxesArrays{tabIdx})
                    return;
                end

                sourceAx = obj.AxesArrays{tabIdx}(subplotIdx);
                if ~isvalid(sourceAx)
                    return;
                end

                % Get save location
                defaultName = sprintf('Tab%d_Plot%d.png', tabIdx, subplotIdx);
                [file, path] = uiputfile({'*.png', 'PNG Files'; '*.jpg', 'JPEG Files'; ...
                    '*.pdf', 'PDF Files'; '*.svg', 'SVG Files'}, ...
                    'Save Plot As', defaultName);

                if isequal(file, 0)
                    return;
                end

                % Create temporary figure for export
                tempFig = figure('Visible', 'off', 'Position', [0 0 800 600], 'Color', [1 1 1]);
                tempAx = axes(tempFig);

                % Copy content excluding highlight borders
                allChildren = allchild(sourceAx);
                validChildren = [];

                % Filter out highlight border lines
                highlightBorders = [];
                if isstruct(sourceAx.UserData) && isfield(sourceAx.UserData, 'HighlightBorders')
                    highlightBorders = sourceAx.UserData.HighlightBorders;
                end

                for i = 1:numel(allChildren)
                    child = allChildren(i);
                    % Only copy if it's not a highlight border
                    if ~any(highlightBorders == child)
                        validChildren = [validChildren; child];
                    end
                end

                % Copy only the valid children
                if ~isempty(validChildren)
                    copyobj(validChildren, tempAx);
                end

                tempAx.XLabel.String = sourceAx.XLabel.String;
                tempAx.YLabel.String = sourceAx.YLabel.String;
                tempAx.Title.String = sprintf('Tab %d - Plot %d', tabIdx, subplotIdx);
                % tempAx.XLim = sourceAx.XLim;
                % tempAx.YLim = sourceAx.YLim;

                % Set normal colors
                tempAx.XColor = [0.15 0.15 0.15];
                tempAx.YColor = [0.15 0.15 0.15];
                tempAx.LineWidth = 1;

                % Save file
                [~, ~, ext] = fileparts(file);
                fullPath = fullfile(path, file);

                switch lower(ext)
                    case '.png'
                        print(tempFig, fullPath, '-dpng', '-r300');
                    case '.jpg'
                        print(tempFig, fullPath, '-djpeg', '-r300');
                    case '.pdf'
                        print(tempFig, fullPath, '-dpdf', '-fillpage');
                    case '.svg'
                        print(tempFig, fullPath, '-dsvg');
                end

                % Clean up
                close(tempFig);

                obj.App.StatusLabel.Text = sprintf('💾 Plot %d saved as %s', subplotIdx, file);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = ['❌ Zoom failed: ' ME.message];
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end


        function clearSubplot(obj, tabIdx, subplotIdx)
            % Clear all signals from a specific subplot
            try
                if tabIdx > numel(obj.AxesArrays) || subplotIdx > numel(obj.AxesArrays{tabIdx})
                    return;
                end

                % Clear assigned signals for this subplot
                obj.AssignedSignals{tabIdx}{subplotIdx} = {};

                % Refresh the plot to show the cleared state
                obj.refreshPlots(tabIdx);

                obj.App.StatusLabel.Text = sprintf('🗑️ Plot %d cleared', subplotIdx);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = ['❌ Clear failed: ' ME.message];
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end

        % Create subplots for a given tab with specified rows and columns
        function createSubplotsForTab(obj, tabIdx, rows, cols)
            % Defensive: check tabIdx
            if tabIdx > numel(obj.PlotTabs)
                return;
            end

            obj.TabLayouts{tabIdx} = [rows, cols];
            obj.ensureAssignedSignalsMatchLayout(tabIdx);


            % Delete old axes and grid layout
            if ~isempty(obj.AxesArrays{tabIdx})
                for ax = obj.AxesArrays{tabIdx}
                    if isvalid(ax)
                        delete(ax);
                    end
                end
            end
            if ~isempty(obj.GridLayouts{tabIdx}) && isvalid(obj.GridLayouts{tabIdx})
                delete(obj.GridLayouts{tabIdx});
            end

            % Get the main layout for this tab
            mainLayout = obj.MainTabGridLayouts{tabIdx};

            % Create the subplot grid inside the second row of the main layout
            plotGrid = uigridlayout(mainLayout, [rows, cols]);
            plotGrid.Layout.Row = 2;
            plotGrid.Layout.Column = 1;
            plotGrid.BackgroundColor = [1 1 1];
            obj.GridLayouts{tabIdx} = plotGrid;

            nPlots = rows * cols;
            obj.AxesArrays{tabIdx} = gobjects(1, nPlots);

            % Initialize limits tracking for this tab
            obj.AxesLimits{tabIdx} = cell(1, nPlots);
            obj.LastDataTime{tabIdx} = cell(1, nPlots);

            % SINGLE LOOP - NOT DUPLICATED
            for i = 1:nPlots
                ax = uiaxes(obj.GridLayouts{tabIdx});
                ax.Layout.Row = ceil(i/cols);
                ax.Layout.Column = mod(i-1, cols)+1;

                % Set up proper axes styling with grid enabled by default
                ax.Color = [1 1 1];
                ax.Box = 'on';
                ax.XLabel.String = 'Time';
                ax.YLabel.String = 'Value';

                % Enable grid and minor grid by default
                grid(ax, 'on');
                ax.XGrid = 'on';
                ax.YGrid = 'on';
                ax.XMinorGrid = 'on';
                ax.YMinorGrid = 'on';
                ax.GridAlpha = 0.3;
                ax.MinorGridAlpha = 0.1;

                % DON'T set any default limits - let MATLAB auto-scale
                ax.XLimMode = 'auto';
                ax.YLimMode = 'auto';

                % *** CRITICAL FIX: Enable interactions for ALL tabs including Tab 1 ***
                try
                    ax.Interactions = [panInteraction, zoomInteraction];
                catch
                    % Fallback for older MATLAB versions
                    ax.Toolbar.Visible = 'on';
                end

                % Initialize limits tracking with empty values
                obj.AxesLimits{tabIdx}{i} = struct('XLim', [], 'YLim', [], 'HasData', false);
                obj.LastDataTime{tabIdx}{i} = 0;

                obj.XAxisSignals{tabIdx, i} = 'Time';

                % Add click callback for subplot selection
                ax.ButtonDownFcn = @(src, event) obj.selectSubplot(tabIdx, i);

                % ADD CONTEXT MENU with all options including zoom
                cm = uicontextmenu(obj.App.UIFigure);

                % Caption editing
                uimenu(cm, 'Text', '📝 Edit Title, Caption & Description', ...
                    'MenuSelectedFcn', @(src, event) obj.App.editSubplotCaption(tabIdx, i));

                % Data tips toggle
                uimenu(cm, 'Text', '🎯 Toggle Data Tips', ...
                    'MenuSelectedFcn', @(src, event) obj.toggleDataTipsForAxes(ax), ...
                    'Separator', 'on');

                % Zoom options - ADD THESE
                uimenu(cm, 'Text', '🔍 Auto Scale This Plot', ...
                    'MenuSelectedFcn', @(src, event) obj.autoScaleSingleSubplot(ax), ...
                    'Separator', 'on');

                uimenu(cm, 'Text', '🔍 Zoom to Fit All Data', ...
                    'MenuSelectedFcn', @(src, event) obj.zoomToFitData(ax));

                % Export options
                uimenu(cm, 'Text', '📊 Export to MATLAB Figure', ...
                    'MenuSelectedFcn', @(src, event) obj.exportSubplotToFigure(tabIdx, i), ...
                    'Separator', 'on');
                uimenu(cm, 'Text', '📋 Copy to Clipboard', ...
                    'MenuSelectedFcn', @(src, event) obj.copySubplotToClipboard(tabIdx, i));
                uimenu(cm, 'Text', '💾 Save as Image', ...
                    'MenuSelectedFcn', @(src, event) obj.saveSubplotAsImage(tabIdx, i));

                uimenu(cm, 'Text', '🗑️ Clear Subplot', ...
                    'MenuSelectedFcn', @(src, event) obj.clearSubplot(tabIdx, i));

                uimenu(cm, 'Text', '⏱️ Reset X-Axis to Time', ...
                    'MenuSelectedFcn', @(src, event) obj.resetXAxisToTime(tabIdx, i), ...
                    'Separator', 'on');

                % IMPORTANT: Set context menu BEFORE enabling any cursor modes
                ax.ContextMenu = cm;
                obj.AxesArrays{tabIdx}(i) = ax;
            end

            % Immediately refresh plots for this tab so checked signals are shown
            obj.App.PlotManager.refreshPlots(tabIdx);
            % Highlight the selected subplot
            obj.App.highlightSelectedSubplot(tabIdx, obj.SelectedSubplotIdx);
            obj.App.initializeCaptionArrays(tabIdx, nPlots);
        end


        function resetXAxisToTime(obj, tabIdx, subplotIdx)
            obj.XAxisSignals{tabIdx, subplotIdx} = 'Time';
            obj.refreshPlots(tabIdx);
        end

        function showPDFExportDialog(obj)
            app = obj.App;

            % Check if there are plots to export
            if obj.CurrentTabIdx > numel(obj.AxesArrays) || isempty(obj.AxesArrays{obj.CurrentTabIdx})
                app.StatusLabel.Text = '⚠️ No plots to export';
                app.StatusLabel.FontColor = [0.9 0.6 0.2];
                return;
            end

            % Create PDF export dialog - English only
            d = dialog('Name', 'PDF Export Options', 'Position', [250 250 650 700]);

            % Title
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 660 610 25], ...
                'String', 'PDF Report Export Options', 'FontSize', 14, 'FontWeight', 'bold');

            % Report settings
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 625 120 20], ...
                'String', 'Report Title:', 'FontWeight', 'bold');
            titleField = uicontrol('Parent', d, 'Style', 'edit', 'Position', [150 625 480 25], ...
                'String', app.PDFReportTitle, 'HorizontalAlignment', 'left', 'FontSize', 11);

            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 590 120 20], ...
                'String', 'Author:', 'FontWeight', 'bold');
            authorField = uicontrol('Parent', d, 'Style', 'edit', 'Position', [150 590 480 25], ...
                'String', app.PDFReportAuthor, 'HorizontalAlignment', 'left', 'FontSize', 11);

            % Figure label language setting
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 555 120 20], ...
                'String', 'Figure Label:', 'FontWeight', 'bold');

            figureLanguageDropdown = uicontrol('Parent', d, 'Style', 'popupmenu', ...
                'Position', [150 555 150 25], ...
                'String', {'Figure', 'איור'}, ...
                'FontSize', 10, 'Value', 1);

            uicontrol('Parent', d, 'Style', 'text', 'Position', [310 555 320 20], ...
                'String', 'Choose label language for "Figure 1:", "Figure 2:" etc.', ...
                'FontSize', 9, 'ForegroundColor', [0.5 0.5 0.5]);

            % Predefined titles
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 520 120 20], ...
                'String', 'Quick Titles:', 'FontSize', 10);

            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Signal Analysis Report', ...
                'Position', [150 520 150 25], 'FontSize', 9, ...
                'Callback', @(~,~) set(titleField, 'String', 'Signal Analysis Report'));

            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Data Analysis Report', ...
                'Position', [310 520 150 25], 'FontSize', 9, ...
                'Callback', @(~,~) set(titleField, 'String', 'Data Analysis Report'));

            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'דוח ניתוח אותות', ...
                'Position', [470 520 150 25], 'FontSize', 9, ...
                'Callback', @(~,~) set(titleField, 'String', 'דוח ניתוח אותות'));

            % Language support note
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 485 610 25], ...
                'String', 'Note: Hebrew text will be automatically right-aligned. You can mix Hebrew and English.', ...
                'FontSize', 9, 'ForegroundColor', [0.2 0.6 0.9]);

            % Export scope options
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 445 610 20], ...
                'String', 'Export Scope:', 'FontSize', 11, 'FontWeight', 'bold');

            % Export option buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 405 610 30], ...
                'String', '📊 Current Tab Only (with captions and titles)', ...
                'Callback', @(~,~) exportPDFAndClose(1));

            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 370 610 30], ...
                'String', '📚 All Tabs (with captions and titles)', ...
                'Callback', @(~,~) exportPDFAndClose(2));

            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 335 610 30], ...
                'String', '📋 Current Tab - Active Subplots Only (with data)', ...
                'Callback', @(~,~) exportPDFAndClose(3));

            uicontrol('Parent', d, 'Style', 'pushbutton', ...
                'Position', [20 300 610 30], ...
                'String', '🗂️ All Tabs - Active Subplots Only (with data)', ...
                'Callback', @(~,~) exportPDFAndClose(4));

            % Options
            includeTableCheck = uicontrol('Parent', d, 'Style', 'checkbox', 'Position', [20 255 610 20], ...
                'String', 'Include signal statistics table', 'Value', 0);

            includeTOCCheck = uicontrol('Parent', d, 'Style', 'checkbox', 'Position', [20 230 610 20], ...
                'String', 'Include table of contents', 'Value', 0);

            % Info text
            uicontrol('Parent', d, 'Style', 'text', 'Position', [20 170 610 50], ...
                'String', 'The PDF will include figure numbers, captions, descriptions, and subplot titles. Each subplot can have its own title and caption that you can edit by right-clicking on the subplot.', ...
                'FontSize', 9, 'HorizontalAlignment', 'center');

            % Buttons
            uicontrol('Parent', d, 'Style', 'pushbutton', 'String', 'Cancel', ...
                'Position', [550 20 80 30], 'Callback', @(~,~) close(d));

            function exportPDFAndClose(option)
                % Save report settings
                app.PDFReportTitle = titleField.String;
                app.PDFReportAuthor = authorField.String;

                % Get figure label language
                figureLabels = {'Figure', 'איור'};
                app.PDFFigureLabel = figureLabels{figureLanguageDropdown.Value};

                % Call appropriate PDF export function
                options = struct();
                options.includeStats = includeTableCheck.Value;
                options.includeTOC = includeTOCCheck.Value;
                options.figureLabel = app.PDFFigureLabel;

                switch option
                    case 1
                        obj.createReportPDF('currentTab', options);
                    case 2
                        obj.createReportPDF('allTabs', options);
                    case 3
                        obj.createReportPDF('currentTabActive', options);
                    case 4
                        obj.createReportPDF('allTabsActive', options);
                end
                close(d);
                app.restoreFocus();
            end
        end
        % **MAIN METHOD: Improved refreshPlots with streaming optimization - NO CLEARING DURING STREAMING**
        function refreshPlots(obj, tabIndices)
            if ~isprop(obj.App, 'DataManager') || isempty(obj.App.DataManager) || ~isvalid(obj.App.DataManager)
                return;
            end
            if nargin < 2
                tabIndices = 1:numel(obj.AxesArrays);
            end
            if isempty(obj.App.DataManager.DataTables) || all(cellfun(@isempty, obj.App.DataManager.DataTables))
                return;
            end

            usedSignalNames = containers.Map();

            % Track axes that need final auto-scaling
            axesToAutoScale = [];

            for tabIdx = tabIndices
                if tabIdx > numel(obj.AxesArrays) || isempty(obj.AxesArrays{tabIdx})
                    continue;
                end
                axesArr = obj.AxesArrays{tabIdx};
                assignments = obj.AssignedSignals{tabIdx};
                n = min(numel(axesArr), numel(assignments));

                for k = 1:n
                    ax = axesArr(k);

                    % Validate axes exists and is valid before proceeding
                    if ~isvalid(ax) || ~isgraphics(ax)
                        continue;
                    end

                    % Store current limits and check streaming state
                    currentXLim = ax.XLim;
                    currentYLim = ax.YLim;
                    hasExistingData = ~isempty(ax.Children);
                    isStreaming = obj.App.DataManager.IsRunning;

                    % **CONDITIONAL CLEARING - only clear if not streaming or no existing data**
                    shouldClearAndRecreate = ~isStreaming || ~hasExistingData;

                    if shouldClearAndRecreate
                        % Full refresh: clear everything
                        delete(ax.Children);
                    end

                    % Restore and maintain grid settings (always)
                    grid(ax, 'on');
                    ax.XGrid = 'on';
                    ax.YGrid = 'on';
                    ax.XMinorGrid = 'on';
                    ax.YMinorGrid = 'on';
                    ax.GridAlpha = 0.3;
                    ax.MinorGridAlpha = 0.1;

                    hold(ax, 'on');
                    assigned = assignments{k};
                    expanded = {};

                    xSignal = obj.XAxisSignals{tabIdx, k};

                    if ischar(xSignal) && strcmp(xSignal, 'Time')
                        ax.XLabel.String = 'Time';
                    elseif isstruct(xSignal) && isfield(xSignal, 'Signal')
                        % ax.XLabel.String = [xSignal.Signal,create_suffix(obj,csvCounter, xSignal.Signal, tabIdx, k,signalSources,currentEnhancedLabel,usedSignalNames)];
                        ax.XLabel.String = [xSignal.Signal];
                    else
                        ax.XLabel.String = 'X';
                    end

                    for idx = 1:numel(assigned)
                        sig = assigned{idx};

                        % Add the assigned signal
                        expanded{end+1} = sig;

                        % Add its explicitly linked signals (if any)
                        if obj.App.LinkingManager.AutoLinkEnabled
                            % optional flag
                            linkedGroup = obj.App.LinkingManager.getLinkedSignals(sig);
                            for l = 1:numel(linkedGroup)
                                if ~isequal(linkedGroup{l}, sig)
                                    expanded{end+1} = linkedGroup{l};
                                end
                            end
                        end
                    end

                    sigs = expanded;


                    if isempty(sigs)
                        % No signals assigned - let axes auto-scale or keep existing limits
                        if shouldClearAndRecreate
                            % Only set defaults if we cleared everything and not streaming
                            if ~isStreaming
                                % Let auto-scaling handle empty axes using helper method
                                obj.forceAutoScale(ax);
                            else
                                % During streaming, keep reasonable defaults
                                % ax.XLim = [0 10];
                                % ax.YLim = [-1 1];
                                ax.XLimMode = 'manual';
                                ax.YLimMode = 'manual';
                            end
                        else
                            % Keep existing limits and remove all signal plots
                            obj.removeAllSignalPlots(ax);
                            % ax.XLim = currentXLim;
                            % ax.YLim = currentYLim;
                            ax.XLimMode = 'manual';
                            ax.YLimMode = 'manual';
                        end
                        hold(ax, 'off');
                        % Set dynamic X-axis label

                        continue;
                    end


                    % Collect all time and value data for limit calculation
                    allTimeData = [];
                    allValueData = [];
                    plotHandles = [];
                    plotLabels = {};
                    assignedSignalNames = {};
                    % Use axes ColorOrder for default colors
                    colorOrder = ax.ColorOrder;
                    nColors = size(colorOrder,1);
                    colorIdx = 1;

                    % Count occurrences of each signal base name
                    baseNameCounts = containers.Map();  % baseName -> count
                    for j = 1:numel(sigs)
                        base = sigs{j}.Signal;
                        if isKey(baseNameCounts, base)
                            baseNameCounts(base) = baseNameCounts(base) + 1;
                        else
                            baseNameCounts(base) = 1;
                        end
                    end


                    % Plot all signals
                    for j = 1:numel(sigs)
                        sigInfo = sigs{j};
                        baseName = sigs{j}.Signal;
                        csvIdx = sigs{j}.CSVIdx;

                        % Determine CSV label
                        if csvIdx == -1
                            csvLabel = 'derived';
                        else
                            [~, ~, ~] = fileparts(obj.App.DataManager.CSVFilePaths{csvIdx});
                        end

                        % Check if suffixing is needed
                        needSuffix = baseNameCounts(baseName) > 1;

                        % Track and generate suffix
                        % Analyze signal naming requirements for this baseName
                        signalSources = {};  % Cell array to store enhanced labels
                        csvCounter = containers.Map('KeyType', 'char', 'ValueType', 'int32');

                        % Collect all sources of this signal name
                        for jj = 1:numel(sigs)
                            if strcmp(sigs{jj}.Signal, baseName)
                                if sigs{jj}.CSVIdx == -1
                                    enhancedLabel = 'derived';
                                else
                                    enhancedLabel = obj.generateEnhancedCSVLabel(sigs{jj}.CSVIdx);
                                end

                                % Add to sources list
                                signalSources{end+1} = enhancedLabel;

                                % Count occurrences per CSV
                                if csvCounter.isKey(enhancedLabel)
                                    csvCounter(enhancedLabel) = csvCounter(enhancedLabel) + 1;
                                else
                                    csvCounter(enhancedLabel) = 1;
                                end
                            end
                        end

                        % Get current signal's enhanced label
                        if csvIdx == -1
                            currentEnhancedLabel = 'derived';
                        else
                            currentEnhancedLabel = obj.generateEnhancedCSVLabel(csvIdx);
                        end

                        % Determine suffix based on signal name conflicts in UI tree
                        suffix = create_suffix(obj,csvCounter, baseName, tabIdx, k,signalSources,currentEnhancedLabel,usedSignalNames);

                        % Final name used for plot/legend
                        sigName = [baseName suffix];
                        assignedSignalNames{end+1} = sigName;

                        % GET SIGNAL DATA (both original and derived)
                        if sigInfo.CSVIdx == -1  % Derived signal
                            [timeData, signalData] = obj.App.SignalOperations.getSignalData(sigName);
                            if isempty(timeData)
                                continue;
                            end
                            validData = true(size(timeData));  % Derived signals are already clean
                        else  % Original signal
                            T = obj.App.DataManager.DataTables{sigInfo.CSVIdx};
                            if ~ismember(baseName, T.Properties.VariableNames)
                                continue;
                            end
                            validData = ~isnan(T.(baseName));
                            if ~any(validData)
                                continue;
                            end
                            timeData = T.Time(validData);
                            signalData = T.(baseName)(validData);
                        end

                        % ============= CONSISTENT X-AXIS HANDLING FOR BOTH SIGNAL TYPES =============
                        % Get the X-axis signal setting for this subplot
                        xAxisSetting = obj.XAxisSignals{tabIdx, k};
                        useTimeAsX = ischar(xAxisSetting) && strcmp(xAxisSetting, 'Time');

                        if useTimeAsX || isempty(xAxisSetting)
                            % Use time as X-axis (default behavior)
                            xData = timeData;

                        elseif isstruct(xAxisSetting) && isfield(xAxisSetting, 'Signal')
                            % Custom X-axis signal requested
                            try
                                % Get the custom X-axis signal data
                                [customXTime, customXData] = obj.App.SignalOperations.getSignalData(xAxisSetting.Signal);

                                if ~isempty(customXTime) && ~isempty(customXData)
                                    % We have valid custom X-axis data

                                    % Check if we need to align time bases
                                    if length(customXTime) == length(timeData) && all(abs(customXTime - timeData) < 1e-6)
                                        % Same time base - no interpolation needed
                                        xData = customXData;
                                    else
                                        % Different time bases - interpolate current signal to match custom X-axis time
                                        try
                                            % Interpolate current signal to custom X-axis time base
                                            interpolatedSignal = interp1(timeData, signalData, customXTime, 'linear', 'extrap');

                                            % Update signal data to match custom X-axis time base
                                            signalData = interpolatedSignal;
                                            timeData = customXTime;  % Update timeData for consistency
                                            xData = customXData;     % Use custom signal as X-axis

                                        catch ME
                                            % Interpolation failed - fallback to time
                                            fprintf('Warning: X-axis interpolation failed for signal %s: %s\n', sigName, ME.message);
                                            xData = timeData;
                                        end
                                    end
                                else
                                    % Custom X-axis signal not found or empty - fallback to time
                                    fprintf('Warning: Custom X-axis signal not found, using time for %s\n', sigName);
                                    xData = timeData;
                                end

                            catch ME
                                % Error getting custom X-axis - fallback to time
                                fprintf('Warning: Error getting custom X-axis for %s: %s\n', sigName, ME.message);
                                xData = timeData;
                            end

                        else
                            % Invalid X-axis setting - fallback to time
                            xData = timeData;
                        end
                        % ============= END CONSISTENT X-AXIS HANDLING =============

                        % Apply scaling
                        scaleFactor = 1.0;
                        if obj.App.DataManager.SignalScaling.isKey(sigName)
                            scaleFactor = obj.App.DataManager.SignalScaling(sigName);
                        end
                        scaledData = signalData * scaleFactor;

                        % Collect data for limit calculation
                        allTimeData = [allTimeData; xData];  % Now consistently using xData
                        allValueData = [allValueData; scaledData];

                        % Use custom color and line width if set
                        color = [];
                        width = 2;
                        if isprop(obj.App, 'SignalStyles') && ~isempty(obj.App.SignalStyles) && isfield(obj.App.SignalStyles, sigName)
                            style = obj.App.SignalStyles.(sigName);
                            if isfield(style, 'Color') && ~isempty(style.Color)
                                color = style.Color;
                                if ischar(color) || isstring(color)
                                    color = str2num(color); %#ok<ST2NM>
                                end
                            end
                            if isfield(style, 'LineWidth')
                                width = style.LineWidth;
                            end
                        end
                        if isempty(color)
                            color = colorOrder(mod(colorIdx-1, nColors)+1, :);
                            colorIdx = colorIdx + 1;
                        end

                        % Check if it's a state signal
                        isStateSignal = false;
                        if obj.App.DataManager.StateSignals.isKey(sigName)
                            isStateSignal = obj.App.DataManager.StateSignals(sigName);
                        end

                        % Always remove existing signal representation (line or xline)
                        obj.removeSignalPlot(ax, sigName);

                        if isStateSignal
                            % State signals: draw vertical xlines
                            obj.plotStateSignalStable(ax, xData, scaledData, color, sigName, currentYLim, width);
                        else
                            % Regular signals: update existing or create new
                            if shouldClearAndRecreate
                                h = plot(ax, xData, scaledData, ...
                                    'LineWidth', width, ...
                                    'Color', color, ...
                                    'DisplayName', sigName);
                                plotHandles(end+1) = h;
                                plotLabels{end+1} = sigName;
                            else
                                h = obj.updateOrCreateSignalPlot(ax, sigName, xData, scaledData, color, width);
                                if ~isempty(h)
                                    plotHandles(end+1) = h;
                                    plotLabels{end+1} = sigName;
                                end
                            end
                        end
                        if (numel(sigs)==1)
                            ax.YLabel.String = (sigName);
                        else
                            ax.YLabel.String = ('Value');
                        end
                    end

                    % Remove plots for signals no longer assigned (only during streaming)
                    if ~shouldClearAndRecreate && isStreaming
                        obj.removeUnassignedSignalPlots(ax, assignedSignalNames);
                    end

                    % Show legend for regular signals
                    if ~isempty(plotHandles)
                        legend(ax, plotHandles, plotLabels, 'Location', 'best');
                    else
                        legend(ax, 'off');
                    end

                    % **Smart limit management - IMPROVED AUTO-SCALING**
                    if ~isempty(allTimeData) && ~isempty(allValueData)
                        if isStreaming
                            % Streaming mode: manually expand limits based on data
                            obj.updateLimitsForStreaming(ax, allTimeData, allValueData, currentXLim, currentYLim, hasExistingData);
                        else
                            % Not streaming: FORCE auto-scaling using helper method
                            obj.forceAutoScale(ax);
                        end
                    else
                        % No data case
                        if hasExistingData && ~shouldClearAndRecreate
                            % Keep existing limits if we have existing data but no new data
                            % ax.XLim = currentXLim;
                            % ax.YLim = currentYLim;
                            ax.XLimMode = 'manual';
                            ax.YLimMode = 'manual';
                        else
                            % Empty plot - handle differently based on streaming state
                            if ~isStreaming
                                % Not streaming and no data: use auto-scale helper for consistency
                                obj.forceAutoScale(ax);
                            else
                                % Streaming but no data: set reasonable defaults
                                % ax.XLim = [0 10];
                                % ax.YLim = [-1 1];
                                ax.XLimMode = 'manual';
                                ax.YLimMode = 'manual';
                            end
                        end
                    end

                    hold(ax, 'off');
                end
            end

            % **SIMPLIFIED: Auto-scale at the end only if needed**
            if ~isempty(axesToAutoScale)
                for ax = axesToAutoScale
                    if isvalid(ax) && isgraphics(ax)
                        ax.XLimMode = 'auto';
                        ax.YLimMode = 'auto';
                        axis(ax, 'auto');
                        ax.XLimMode = 'manual';
                        ax.YLimMode = 'manual';
                    end
                end
                % Single drawnow at the very end
                drawnow;
            end

            % Link all axes in all tabs on the x-axis
            obj.linkAllAxes();

            % Restore highlight after refresh
            obj.App.highlightSelectedSubplot(obj.CurrentTabIdx, obj.SelectedSubplotIdx);
            autoScaleCurrentSubplot(obj.App);
        end
        function suffix = create_suffix(obj, csvCounter,baseName, tabIdx, k,signalSources,currentEnhancedLabel,usedSignalNames)
            % Check if this signal name exists elsewhere in the UI tree (across all tabs/axes)
            hasConflictInUITree = obj.checkSignalNameConflictInUITree(baseName, tabIdx, k);

            % Apply suffix if there are multiple sources OR if there's a conflict in UI tree
            needSuffix = length(signalSources) > 1 || hasConflictInUITree;

            if needSuffix
                % Count how many different CSVs have this signal
                uniqueCSVs = unique(signalSources);
                currentCSVCount = csvCounter(currentEnhancedLabel);

                if length(uniqueCSVs) == 1 && ~hasConflictInUITree
                    % Case 1: Multiple signals from SAME CSV → use _1, _2, _3...
                    if ~isKey(usedSignalNames, baseName)
                        % First occurrence from this CSV
                        usedSignalNames(baseName) = struct('csvCounters', containers.Map('KeyType', 'char', 'ValueType', 'int32'));
                    end

                    info = usedSignalNames(baseName);
                    csvCounters = info.csvCounters;

                    if csvCounters.isKey(currentEnhancedLabel)
                        counter = csvCounters(currentEnhancedLabel) + 1;
                    else
                        counter = 1;
                    end
                    csvCounters(currentEnhancedLabel) = counter;

                    % Update the stored info
                    info.csvCounters = csvCounters;
                    usedSignalNames(baseName) = info;

                    suffix = ['_{' num2str(counter),'}'];

                else
                    % Case 2, 3, or UI tree conflict: Multiple signals from DIFFERENT CSVs or conflict exists
                    if currentCSVCount > 1
                        % This CSV has multiple instances - need both CSV name and counter
                        if ~isKey(usedSignalNames, baseName)
                            usedSignalNames(baseName) = struct('csvCounters', containers.Map('KeyType', 'char', 'ValueType', 'int32'));
                        end

                        info = usedSignalNames(baseName);
                        csvCounters = info.csvCounters;

                        if csvCounters.isKey(currentEnhancedLabel)
                            counter = csvCounters(currentEnhancedLabel) + 1;
                        else
                            counter = 1;
                        end
                        csvCounters(currentEnhancedLabel) = counter;

                        % Update the stored info
                        info.csvCounters = csvCounters;
                        usedSignalNames(baseName) = info;

                        suffix = ['_{' currentEnhancedLabel '_' num2str(counter),'}'];
                    else
                        % Single instance from this CSV → use CSV name (possibly with folder)
                        suffix = ['_{' currentEnhancedLabel,'}'];
                    end
                end
            else
                % Only one instance total and no UI tree conflict - no suffix needed
                suffix = '';
            end
        end
        function success = forceAutoScale(~, ax)
            % Force auto-scaling on an axes - same logic as AutoScaleButton
            success = false;
            try
                if isvalid(ax) && isgraphics(ax) && ~isempty(ax.Children)
                    % Force auto-scaling
                    ax.XLimMode = 'auto';
                    ax.YLimMode = 'auto';
                    axis(ax, 'auto');

                    % Small pause to ensure auto-scaling completes
                    pause(0.005);

                    % Switch back to manual to prevent future automatic changes
                    ax.XLimMode = 'manual';
                    ax.YLimMode = 'manual';

                    success = true; % Successfully auto-scaled
                end
            catch ME
                % Log error but don't fail
                fprintf('Warning: Auto-scale failed for axes: %s\n', ME.message);
            end
        end

        function showDerivedSignalMenu(obj, tabIdx, subplotIdx)
            % Show submenu for creating derived signals from current subplot
            if tabIdx <= numel(obj.AssignedSignals) && subplotIdx <= numel(obj.AssignedSignals{tabIdx})
                assignedSignals = obj.AssignedSignals{tabIdx}{subplotIdx};
                if ~isempty(assignedSignals)
                    % Create context submenu
                    cm = uicontextmenu(obj.App.UIFigure);
                    uimenu(cm, 'Text', '∂ Derivative', 'MenuSelectedFcn', @(~,~) obj.App.SignalOperations.showSingleSignalDialog('derivative'));
                    uimenu(cm, 'Text', '∫ Integral', 'MenuSelectedFcn', @(~,~) obj.App.SignalOperations.showSingleSignalDialog('integral'));
                    if length(assignedSignals) >= 2
                        uimenu(cm, 'Text', '− Subtract', 'MenuSelectedFcn', @(~,~) obj.App.SignalOperations.showDualSignalDialog('subtract'));
                        uimenu(cm, 'Text', '‖‖ Norm', 'MenuSelectedFcn', @(~,~) obj.App.SignalOperations.showNormDialog());
                    end
                    uimenu(cm, 'Text', '💻 Custom Code', 'MenuSelectedFcn', @(~,~) obj.App.SignalOperations.showCustomCodeDialog());

                    % Show the menu at mouse position
                    cm.Visible = 'on';
                else
                    uialert(obj.App.UIFigure, 'No signals assigned to this subplot.', 'No Signals');
                end
            end
        end

        function onTabLayoutChanged(obj, tabIdx, newRows, newCols)
            % Handle layout changes from tab-specific controls
            currentLayout = obj.TabLayouts{tabIdx};

            if ~isempty(newRows)
                rows = newRows;
                cols = currentLayout(2);
                % Update the cols spinner to match current value
                if isfield(obj.TabControls{tabIdx}, 'ColsSpinner')
                    obj.TabControls{tabIdx}.ColsSpinner.Value = cols;
                end
            elseif ~isempty(newCols)
                rows = currentLayout(1);
                cols = newCols;
                % Update the rows spinner to match current value
                if isfield(obj.TabControls{tabIdx}, 'RowsSpinner')
                    obj.TabControls{tabIdx}.RowsSpinner.Value = rows;
                end
            else
                return;
            end

            % Apply the layout change
            obj.createSubplotsForTab(tabIdx, rows, cols);

            % Update the subplot dropdown
            obj.updateTabSubplotDropdown(tabIdx);

            % Refresh plots if there are any signals assigned
            obj.App.PlotManager.refreshPlots(tabIdx);

            % Update per-tab axis linking after layout change
            obj.updateTabLinkAxes(tabIdx);

            % Highlight the current subplot
            obj.App.highlightSelectedSubplot(tabIdx, obj.SelectedSubplotIdx);
        end

        function onSubplotSelected(obj, tabIdx, selectedValue)
            % Handle subplot selection from tab-specific dropdown
            plotNum = str2double(regexp(selectedValue, '\d+', 'match', 'once'));
            if ~isempty(plotNum) && plotNum > 0
                obj.SelectedSubplotIdx = plotNum;
                obj.App.highlightSelectedSubplot(tabIdx, plotNum);
            end
        end

        function updateTabSubplotDropdown(obj, tabIdx)
            % Update the subplot dropdown for a specific tab
            if tabIdx <= numel(obj.TabControls) && ~isempty(obj.TabControls{tabIdx})
                nPlots = obj.TabLayouts{tabIdx}(1) * obj.TabLayouts{tabIdx}(2);
                plotItems = cell(nPlots, 1);
                for i = 1:nPlots
                    plotItems{i} = sprintf('Plot %d', i);
                end

                dropdown = obj.TabControls{tabIdx}.SubplotDropdown;
                dropdown.Items = plotItems;

                % Ensure selected subplot is within bounds
                if obj.SelectedSubplotIdx > nPlots
                    obj.SelectedSubplotIdx = 1;
                end
                dropdown.Value = sprintf('Plot %d', obj.SelectedSubplotIdx);
            end
        end

        % **NEW METHOD: Update existing signal plot or create new one**
        function h = updateOrCreateSignalPlot(obj, ax, sigName, timeData, scaledData, color, width)
            % Find existing line for this signal
            existingLine = obj.findSignalPlot(ax, sigName);

            if ~isempty(existingLine)
                % Update existing line data
                existingLine.XData = timeData;
                existingLine.YData = scaledData;
                existingLine.Color = color;
                existingLine.LineWidth = width;
                h = existingLine;
            else
                % Create new line
                h = plot(ax, timeData, scaledData, 'LineWidth', width, 'Color', color, 'DisplayName', sigName);
            end
        end

        % **NEW METHOD: Find existing signal plot by name**
        function line = findSignalPlot(~, ax, sigName)
            line = [];
            if isempty(ax.Children)
                return;
            end

            % Look for line with matching DisplayName
            for i = 1:numel(ax.Children)
                child = ax.Children(i);
                if isa(child, 'matlab.graphics.chart.primitive.Line') && ...
                        isprop(child, 'DisplayName') && ...
                        strcmp(child.DisplayName, sigName)
                    line = child;
                    return;
                end
            end
        end

        % **NEW METHOD: Remove specific signal plot**
        function removeSignalPlot(obj, ax, sigName)
            % Remove regular plot line
            line = obj.findSignalPlot(ax, sigName);
            if ~isempty(line) && isvalid(line)
                delete(line);
            end

            % Remove any matching xline objects tagged with the signal name
            allXLines = findall(ax, 'Type', 'ConstantLine');  % includes xline
            for k = 1:numel(allXLines)
                h = allXLines(k);
                if isprop(h, 'Tag') && strcmp(h.Tag, ['state_' sigName])
                    delete(h);
                end
            end
        end


        % **NEW METHOD: Remove all signal plots**
        function removeAllSignalPlots(~, ax)
            if isempty(ax.Children)
                return;
            end

            % Delete all line objects
            linesToDelete = [];
            for i = 1:numel(ax.Children)
                child = ax.Children(i);
                if isa(child, 'matlab.graphics.chart.primitive.Line')
                    linesToDelete = [linesToDelete, child];
                end
            end

            for line = linesToDelete
                if isvalid(line)
                    delete(line);
                end
            end
        end

        % **NEW METHOD: Remove plots for unassigned signals**
        function removeUnassignedSignalPlots(~, ax, assignedSignalNames)
            if isempty(ax.Children)
                return;
            end

            % Find lines and xlines not in the assigned list
            itemsToDelete = [];
            for i = 1:numel(ax.Children)
                child = ax.Children(i);
                isLine = strcmp(child.Type, 'line');
                isXLine = strcmp(child.Type, 'constantline');  % More robust than isa()

                if (isLine || isXLine) && ...
                        isprop(child, 'DisplayName') && ...
                        ~isempty(child.DisplayName) && ...
                        ~ismember(child.DisplayName, assignedSignalNames)
                    itemsToDelete = [itemsToDelete, child]; %#ok<AGROW>
                end
            end

            % Delete unassigned plots/xlines
            for item = itemsToDelete
                if isvalid(item)
                    delete(item);
                end
            end
        end

        % **NEW METHOD: Update limits during streaming**
        function updateLimitsForStreaming(~, ax, allTimeData, allValueData, currentXLim, currentYLim, hasExistingData)
            % Calculate new limits based on data
            dataXMin = min(allTimeData);
            dataXMax = max(allTimeData);
            dataYMin = min(allValueData);
            dataYMax = max(allValueData);

            % Calculate ranges and padding
            xRange = dataXMax - dataXMin;
            yRange = dataYMax - dataYMin;

            if xRange > 0
                xPadding = 0.05 * xRange;
                newXLim = [dataXMin - xPadding, dataXMax + xPadding];
            else
                newXLim = [dataXMin - 1, dataXMax + 1];
            end

            if yRange > 0
                yPadding = 0.1 * yRange;
                newYLim = [dataYMin - yPadding, dataYMax + yPadding];
            else
                newYLim = [dataYMin - 0.1, dataYMax + 0.1];
            end

            % During streaming: expand limits if needed, don't shrink
            if hasExistingData
                finalXLim = [min(currentXLim(1), newXLim(1)), max(currentXLim(2), newXLim(2))];
                finalYLim = [min(currentYLim(1), newYLim(1)), max(currentYLim(2), newYLim(2))];
            else
                finalXLim = newXLim;
                finalYLim = newYLim;
            end

            % Set limits
            % ax.XLim = finalXLim;
            % ax.YLim = finalYLim;
            ax.XLimMode = 'manual';
            ax.YLimMode = 'manual';
        end

        % **UPDATED METHOD: Per-tab axis linking**
        function linkAllAxes(obj)
            % This function is now deprecated in favor of per-tab linking
            % Apply per-tab linking for all tabs based on their individual settings
            for i = 1:numel(obj.AxesArrays)
                if i <= length(obj.TabLinkedAxes) && obj.TabLinkedAxes(i)
                    obj.linkTabAxes(i);
                end
            end
        end


        % **UPDATED METHOD: Improved state signal plotting**
        function plotStateSignalStable(~, ax, timeData, valueData, color, label, ~, lineWidth)
            if isempty(timeData)
                return;
            end

            % Use a tolerance to detect state changes
            changeIdx = find([true; abs(diff(valueData)) > 1e-8]);

            % If all values are the same, use only the first timestamp
            if isempty(changeIdx)
                changeTimes = timeData(1);
            else
                changeTimes = timeData(changeIdx);
            end

            for k = 1:numel(changeTimes)
                t = changeTimes(k);
                h = xline(ax, t, '--', ...
                    'Color', color, ...
                    'LineWidth', lineWidth, ...
                    'Alpha', 0.6, ...
                    'Label', label, ...
                    'DisplayName', label, ...
                    'LabelOrientation', 'horizontal', ...
                    'LabelVerticalAlignment', 'middle');

                % Only the first xline gets the label
                if k > 1
                    h.Label = '';
                end

                % Optional: Tag the line for easier cleanup
                h.Tag = ['state_' label];
            end
        end


        function updateAllPlotsForStreaming(obj)
            % Optimized streaming updates - uses existing line update mechanism
            obj.refreshPlots();
        end

        function selectSubplot(obj, tabIdx, subplotIdx)
            % Update the selected subplot index
            obj.SelectedSubplotIdx = subplotIdx;

            % Clear ALL highlights in this tab first
            obj.App.clearSubplotHighlights(tabIdx);

            % Highlight the newly selected subplot
            obj.App.highlightSelectedSubplot(tabIdx, subplotIdx);

            % Update the tab-specific subplot dropdown
            if tabIdx <= numel(obj.TabControls) && ~isempty(obj.TabControls{tabIdx}) && ...
                    isfield(obj.TabControls{tabIdx}, 'SubplotDropdown')

                val = sprintf('Plot %d', subplotIdx);
                dropdown = obj.TabControls{tabIdx}.SubplotDropdown;

                if any(strcmp(val, dropdown.Items))
                    dropdown.Value = val;
                end
            end

            % Update signal tree for the newly selected subplot
            obj.updateSignalTreeForCurrentTab();
        end

        function addNewTab(obj, ~, ~)
            rows = 2; cols = 1;

            % Count real tabs (excluding + tab)
            realTabCount = 0;
            for i = 1:numel(obj.PlotTabs)
                if ~strcmp(obj.PlotTabs{i}.Title, '+')
                    realTabCount = realTabCount + 1;
                end
            end

            newTabNum = realTabCount + 1;

            % Create new tab WITHOUT X in title initially
            tab = uitab(obj.App.MainTabGroup, 'Title', sprintf('Tab %d', newTabNum), ...
                'BackgroundColor', [0.98 0.98 0.98]);

            % Find + tab position
            plusTabIdx = find(cellfun(@(t) strcmp(t.Title, '+'), obj.PlotTabs));

            if ~isempty(plusTabIdx)
                % Insert new tab before + tab
                newTabIdx = plusTabIdx;
                obj.PlotTabs = [obj.PlotTabs(1:plusTabIdx-1), {tab}, obj.PlotTabs(plusTabIdx:end)];
                obj.GridLayouts = [obj.GridLayouts(1:plusTabIdx-1), {[]}, obj.GridLayouts(plusTabIdx:end)];
                obj.AxesArrays = [obj.AxesArrays(1:plusTabIdx-1), {matlab.ui.control.UIAxes.empty}, obj.AxesArrays(plusTabIdx:end)];
                obj.AssignedSignals = [obj.AssignedSignals(1:plusTabIdx-1), {{}}, obj.AssignedSignals(plusTabIdx:end)];
                obj.TabLayouts = [obj.TabLayouts(1:plusTabIdx-1), {[rows, cols]}, obj.TabLayouts(plusTabIdx:end)];
                obj.AxesLimits = [obj.AxesLimits(1:plusTabIdx-1), {{}}, obj.AxesLimits(plusTabIdx:end)];
                obj.LastDataTime = [obj.LastDataTime(1:plusTabIdx-1), {{}}, obj.LastDataTime(plusTabIdx:end)];
                obj.TabControls = [obj.TabControls(1:plusTabIdx-1), {[]}, obj.TabControls(plusTabIdx:end)];
                obj.MainTabGridLayouts = [obj.MainTabGridLayouts(1:plusTabIdx-1), {[]}, obj.MainTabGridLayouts(plusTabIdx:end)];
            else
                % Add to end (no + tab exists)
                newTabIdx = numel(obj.PlotTabs) + 1;
                obj.PlotTabs{end+1} = tab;
                obj.GridLayouts{end+1} = [];
                obj.AxesArrays{end+1} = matlab.ui.control.UIAxes.empty;
                obj.AssignedSignals{end+1} = {};
                obj.TabLayouts{end+1} = [rows, cols];
                obj.AxesLimits{end+1} = {};
                obj.LastDataTime{end+1} = {};
                obj.TabControls{end+1} = [];
                obj.MainTabGridLayouts{end+1} = [];
            end

            % Create main layout for the new tab WITH FIXED CONTROL HEIGHT
            mainLayout = uigridlayout(tab, [2, 1]);
            mainLayout.RowHeight = {60, '1x'}; % FIXED: Top row 60px, Bottom fills remaining space
            mainLayout.ColumnWidth = {'1x'};
            obj.MainTabGridLayouts{newTabIdx} = mainLayout;

            % Initialize assigned signals for new tab
            nPlots = rows * cols;
            obj.AssignedSignals{newTabIdx} = cell(nPlots, 1);
            for i = 1:nPlots
                obj.AssignedSignals{newTabIdx}{i} = {};
            end

            % Initialize per-tab linking state for new tab
            while length(obj.TabLinkedAxes) < newTabIdx
                obj.TabLinkedAxes(end+1) = false;
                obj.TabLinkedAxesObjects{end+1} = [];
            end

            % *** ADD THIS LINE HERE - BEFORE addTabControls: ***
            obj.validateSelectedSubplotIdx(newTabIdx);

            % Add tab-specific controls FIRST (they go in row 1)
            obj.addTabControls(newTabIdx);

            % THEN create subplots (they go in row 2)
            obj.createSubplotsForTab(newTabIdx, rows, cols);

            % Switch to the new tab
            obj.CurrentTabIdx = newTabIdx;
            obj.App.MainTabGroup.SelectedTab = tab;

            % Ensure + tab is at the end and UI is ordered correctly
            obj.ensurePlusTabAtEnd();

            % Update tab titles to show X icons appropriately
            obj.updateTabTitles();

            % Update signal tree for the new tab
            obj.updateSignalTreeForCurrentTab();

            % Update per-tab axis linking for the new tab
            obj.updateTabLinkAxes(newTabIdx);
        end

        function updateTabTitles(obj)
            % Update tab titles - NO X icons, use double-click to close
            realTabs = [];

            % Find all real tabs (not + tabs)
            for i = 1:numel(obj.PlotTabs)
                if ~strcmp(obj.PlotTabs{i}.Title, '+') && ~contains(obj.PlotTabs{i}.Title, '+')
                    realTabs = [realTabs i];
                end
            end

            % Update titles based on number of real tabs
            for i = 1:numel(realTabs)
                tabIdx = realTabs(i);
                tab = obj.PlotTabs{tabIdx};

                if numel(realTabs) > 1
                    % Multiple tabs: show clean title and add double-click callback
                    tab.Title = sprintf('Tab %d', i);

                    % Add double-click callback for closing
                    try
                        tab.ButtonDownFcn = @(src, event) obj.handleTabClick(tab, event);
                    end

                else
                    % Only one tab: clean title, no close functionality
                    tab.Title = sprintf('Tab %d', i);
                    tab.ButtonDownFcn = [];
                end
            end
        end

        function handleTabClick(obj, tab, event)
            % Handle tab clicks - double-click to close, Ctrl+Click for quick close
            persistent lastClickTime lastClickedTab

            currentTime = now;

            % Check for Ctrl+Click (quick delete)
            if ~isempty(event) && isfield(event, 'Source') && isprop(event.Source, 'CurrentModifier')
                modifiers = event.Source.CurrentModifier;
                if any(strcmp(modifiers, 'control'))
                    obj.deleteTabByHandle(tab);
                    return;
                end
            end

            % Check if this is a double-click (within 0.5 seconds)
            if ~isempty(lastClickTime) && ~isempty(lastClickedTab) && ...
                    (currentTime - lastClickTime) < (0.5/86400) && ...
                    lastClickedTab == tab

                % Double-click detected - close the tab
                obj.deleteTabByHandle(tab);

                % Reset
                lastClickTime = [];
                lastClickedTab = [];
            else
                % Single click - just record the time and tab
                lastClickTime = currentTime;
                lastClickedTab = tab;
            end
        end
        function reorderUITabs(obj)
            % Reorder the actual UI tabs to match our PlotTabs array order
            tabGroup = obj.App.MainTabGroup;

            % Get current children and reorder them
            for i = 1:numel(obj.PlotTabs)
                tab = obj.PlotTabs{i};
                if isvalid(tab)
                    % Move tab to correct position in the UI
                    uistack(tab, 'bottom');
                end
            end

            % Now stack them in reverse order to get correct left-to-right order
            for i = numel(obj.PlotTabs):-1:1
                tab = obj.PlotTabs{i};
                if isvalid(tab)
                    uistack(tab, 'top');
                end
            end
        end

        function deleteCurrentTab(obj)
            if numel(obj.PlotTabs) <= 2
                return;
            end

            currentIdx = obj.CurrentTabIdx;
            if strcmp(obj.PlotTabs{currentIdx}.Title, '+')
                return;
            end

            delete(obj.PlotTabs{currentIdx});
            obj.PlotTabs(currentIdx) = [];
            obj.GridLayouts(currentIdx) = [];
            obj.AxesArrays(currentIdx) = [];
            obj.AssignedSignals(currentIdx) = [];
            obj.TabLayouts(currentIdx) = [];
            obj.AxesLimits(currentIdx) = [];
            obj.LastDataTime(currentIdx) = [];

            if currentIdx > numel(obj.PlotTabs)-1
                obj.CurrentTabIdx = numel(obj.PlotTabs)-1;
            end

            obj.App.MainTabGroup.SelectedTab = obj.PlotTabs{obj.CurrentTabIdx};
            obj.ensurePlusTab();
        end

        function deleteTabByHandle(obj, tab)
            idx = find(cellfun(@(t) t == tab, obj.PlotTabs));
            if ~isempty(idx)
                % Don't allow deleting if it's the + tab
                if strcmp(tab.Title, '+') || contains(tab.Title, '+')
                    return;
                end

                % Count real tabs
                realTabs = 0;
                for i = 1:numel(obj.PlotTabs)
                    if ~strcmp(obj.PlotTabs{i}.Title, '+') && ~contains(obj.PlotTabs{i}.Title, '+')
                        realTabs = realTabs + 1;
                    end
                end

                % Don't allow deleting the last real tab
                if realTabs <= 1
                    return;
                end

                % Delete the tab
                delete(tab);

                % *** IMPORTANT: Remove from ALL arrays at the same index ***
                obj.PlotTabs(idx) = [];

                % Only remove from other arrays if within bounds
                if idx <= numel(obj.GridLayouts)
                    obj.GridLayouts(idx) = [];
                end
                if idx <= numel(obj.AxesArrays)
                    obj.AxesArrays(idx) = [];
                end
                if idx <= numel(obj.AssignedSignals)
                    obj.AssignedSignals(idx) = [];
                end
                if idx <= numel(obj.TabLayouts)
                    obj.TabLayouts(idx) = [];
                end
                if idx <= numel(obj.AxesLimits)
                    obj.AxesLimits(idx) = [];
                end
                if idx <= numel(obj.LastDataTime)
                    obj.LastDataTime(idx) = [];
                end
                if idx <= numel(obj.TabControls)
                    obj.TabControls(idx) = [];
                end
                if idx <= numel(obj.MainTabGridLayouts)
                    obj.MainTabGridLayouts(idx) = [];
                end

                % *** CRITICAL: Also clean up linking arrays ***
                if idx <= length(obj.TabLinkedAxes)
                    obj.TabLinkedAxes(idx) = [];
                end
                if idx <= length(obj.TabLinkedAxesObjects)
                    obj.TabLinkedAxesObjects(idx) = [];
                end

                % Adjust current tab index if necessary
                if obj.CurrentTabIdx >= idx
                    obj.CurrentTabIdx = max(1, obj.CurrentTabIdx - 1);
                end

                % Switch to a valid tab
                validTabFound = false;
                for i = 1:numel(obj.PlotTabs)
                    if ~strcmp(obj.PlotTabs{i}.Title, '+') && ~contains(obj.PlotTabs{i}.Title, '+')
                        obj.CurrentTabIdx = i;
                        obj.App.MainTabGroup.SelectedTab = obj.PlotTabs{i};
                        validTabFound = true;
                        break;
                    end
                end

                if ~validTabFound
                    % If no valid tab found, create a new one
                    obj.createFirstTab();
                    return;
                end

                % Update tab titles
                obj.updateTabTitles();

                % Ensure + tab stays at the end
                obj.ensurePlusTabAtEnd();

                % Update UI
                if ismethod(obj.App.UIController, 'updateSubplotDropdown')
                    obj.App.UIController.updateSubplotDropdown();
                end
                obj.updateSignalTreeForCurrentTab();

                % Important: Refresh current tab to ensure everything works
                obj.validateAndFixSubplotIndex();
            end
        end

        % FIX 5: Add validation method to clean up after deletions

        function validateAndFixSubplotIndex(obj)
            % Ensure SelectedSubplotIdx is valid for current tab after deletions
            tabIdx = obj.CurrentTabIdx;

            if tabIdx <= numel(obj.AssignedSignals) && ~isempty(obj.AssignedSignals{tabIdx})
                maxSubplotIdx = numel(obj.AssignedSignals{tabIdx});

                if obj.SelectedSubplotIdx > maxSubplotIdx
                    obj.SelectedSubplotIdx = 1;

                    % Update dropdown if it exists
                    if tabIdx <= numel(obj.TabControls) && ~isempty(obj.TabControls{tabIdx}) && ...
                            isfield(obj.TabControls{tabIdx}, 'SubplotDropdown')
                        obj.TabControls{tabIdx}.SubplotDropdown.Value = 'Plot 1';
                    end
                end
            end
        end

        function changeTabLayout(obj, tabIdx, rows, cols)
            if tabIdx <= numel(obj.PlotTabs)
                obj.createSubplotsForTab(tabIdx, rows, cols);
            end
        end

        function exportToPDF(obj)
            % Show PDF export dialog instead of direct export
            obj.showPDFExportDialog();
        end

        function exportTabsToPlotBrowser(obj)
            if isempty(obj.AxesArrays)
                uialert(obj.App.UIFigure, 'No plots to export.', 'Export Error');
                return;
            end

            numTabs = numel(obj.AxesArrays);

            for tabIdx = 1:numTabs
                axesArray = obj.AxesArrays{tabIdx};
                if isempty(axesArray) || ~any(isgraphics(axesArray, 'axes'))
                    continue;
                end

                % Create new figure for this tab
                fig = figure('Name', sprintf('Plot Browser - Tab %d', tabIdx), ...
                    'NumberTitle', 'off', ...
                    'Color', 'w', ...
                    'Units', 'normalized', ...
                    'Position', [0.1 0.1 0.8 0.8]);

                % Create subplot layout
                numSubplots = numel(axesArray);
                rows = ceil(sqrt(numSubplots));
                cols = ceil(numSubplots / rows);

                for i = 1:numSubplots
                    oldAx = axesArray(i);
                    if ~isgraphics(oldAx, 'axes')
                        continue;
                    end

                    newAx = subplot(rows, cols, i, 'Parent', fig);
                    titleStr = oldAx.Title.String;
                    if isempty(titleStr)
                        titleStr = sprintf('Subplot %d', i);
                    end
                    title(newAx, titleStr);
                    xlabel(newAx, oldAx.XLabel.String);
                    ylabel(newAx, oldAx.YLabel.String);

                    % === Apply styling ===
                    % grid(newAx, 'on');
                    % grid(newAx, 'minor');
                    % box(newAx, 'on');

                    % Copy line objects
                    lines = findall(oldAx, 'Type', 'line');
                    for line = flipud(lines')  % preserve draw order
                        plot(newAx, line.XData, line.YData, ...
                            'DisplayName', line.DisplayName, ...
                            'Color', line.Color, ...
                            'LineWidth', line.LineWidth, ...
                            'LineStyle', line.LineStyle);
                    end
                    grid on; grid minor; box on;

                    legend(newAx, 'show');
                end

                % Turn on the Plot Browser
                plotbrowser(fig, 'on');
            end
        end

        function exportToSDI(obj)
            % Export signals from signal tree to Simulink Data Inspector
            % Uses addToRun instead of addSignal for better control and metadata
            Simulink.sdi.clear;

            app = obj.App;

            try
                % Check if we have any data to export
                if isempty(app.DataManager.DataTables) || all(cellfun(@isempty, app.DataManager.DataTables))
                    uialert(app.UIFigure, 'No data available to export to SDI.', 'No Data');
                    return;
                end

                % Check if SDI is available
                if ~license('test', 'Simulink')
                    uialert(app.UIFigure, 'Simulink Data Inspector requires Simulink license.', 'License Required');
                    return;
                end

                rootNodes = app.SignalTree.Children;

                if isempty(rootNodes)
                    uialert(app.UIFigure, 'No signals found in signal tree.', 'No Signals');
                    return;
                end

                totalSignalsAdded = 0;

                % Process each root node (CSV file)
                for i = 1:numel(rootNodes)
                    csvNode = rootNodes(i);
                    csvName = string(csvNode.Text);

                    % Skip derived signals folder for now
                    if contains(csvName, 'Derived Signals') || contains(csvName, '⚙️')
                        continue;
                    end

                    % Create SDI run per CSV with metadata
                    try
                        % Basic createRun call - some MATLAB versions don't support name-value pairs
                        runID = Simulink.sdi.createRun(char(csvName));

                        fprintf('Processing CSV: %s (Run ID: %d)\n', csvName, runID);

                        % Recursively add signals
                        signalCount = traverse(csvNode, csvName, runID);
                        totalSignalsAdded = totalSignalsAdded + signalCount;

                        fprintf('  Added %d signals to run\n', signalCount);

                    catch ME
                        fprintf('Error creating run for %s: %s\n', csvName, ME.message);
                        continue;
                    end
                end

                if totalSignalsAdded > 0
                    % Open SDI view
                    try
                        Simulink.sdi.view;
                        app.StatusLabel.Text = sprintf('✅ Exported %d signals to SDI', totalSignalsAdded);
                        app.StatusLabel.FontColor = [0.2 0.6 0.9];
                    catch
                        app.StatusLabel.Text = sprintf('✅ Exported %d signals to SDI (manual view required)', totalSignalsAdded);
                        app.StatusLabel.FontColor = [0.2 0.6 0.9];
                    end
                else
                    app.StatusLabel.Text = '⚠️ No signals were exported to SDI';
                    app.StatusLabel.FontColor = [0.9 0.6 0.2];
                end

            catch ME
                fprintf('Error in exportToSDI: %s\n', ME.message);
                app.StatusLabel.Text = sprintf('❌ SDI export failed: %s', ME.message);
                app.StatusLabel.FontColor = [0.9 0.3 0.3];

                % Show detailed error dialog
                uialert(app.UIFigure, sprintf('Export to SDI failed:\n%s', ME.message), 'Export Error');
            end

            % ---------- Nested helper function ----------
            function count = traverse(node, prefix, runID)
                count = 0;

                if isempty(node.Children)
                    return;
                end

                for j = 1:numel(node.Children)
                    child = node.Children(j);
                    childName = string(child.Text);

                    % Remove any checkmarks from the display name
                    cleanChildName = strrep(childName, '✔ ', '');
                    fullName = prefix + "/" + cleanChildName;

                    if isempty(child.Children)
                        % It's a signal leaf - process it
                        if processSignalLeaf(child, fullName, runID)
                            count = count + 1;
                        end
                    else
                        % Recurse into child nodes (shouldn't happen in current structure)
                        count = count + traverse(child, fullName, runID);
                    end
                end
            end

            % ---------- Signal processing helper ----------
            function success = processSignalLeaf(node, fullName, runID)
                success = false;

                try
                    % Validate node structure
                    if ~isprop(node, 'NodeData') || isempty(node.NodeData)
                        return;
                    end

                    signalStruct = node.NodeData;

                    % Validate signal structure
                    if ~isstruct(signalStruct) || ~isfield(signalStruct, "CSVIdx") || ~isfield(signalStruct, "Signal")
                        return;
                    end

                    csvIdx = signalStruct.CSVIdx;
                    baseName = signalStruct.Signal;

                    % Get signal data based on type
                    if csvIdx == -1
                        % Derived signal - skip for now or handle separately
                        fprintf('  Skipping derived signal: %s\n', baseName);
                        return;
                    else
                        % CSV signal
                        if csvIdx > length(app.DataManager.DataTables) || csvIdx < 1
                            fprintf('  Warning: Invalid CSV index %d for signal %s\n', csvIdx, fullName);
                            return;
                        end

                        T = app.DataManager.DataTables{csvIdx};

                        if isempty(T) || ~ismember(baseName, T.Properties.VariableNames)
                            fprintf('  Warning: Signal %s not found in CSV %d\n', baseName, csvIdx);
                            return;
                        end

                        timeData = T.Time;
                        signalData = T.(baseName);
                    end

                    % Validate and clean data
                    if isempty(timeData) || isempty(signalData) || length(timeData) ~= length(signalData)
                        fprintf('  Warning: Invalid data dimensions for signal %s\n', fullName);
                        return;
                    end

                    % Remove NaN values
                    valid = ~isnan(timeData) & ~isnan(signalData) & isfinite(timeData) & isfinite(signalData);

                    if ~any(valid)
                        fprintf('  Warning: No valid data points for signal %s\n', fullName);
                        return;
                    end

                    % Clean data
                    timeData = timeData(valid);
                    signalData = signalData(valid);

                    % Apply scaling if it exists
                    if isfield(app.DataManager, 'SignalScaling') && ...
                            isa(app.DataManager.SignalScaling, 'containers.Map') && ...
                            app.DataManager.SignalScaling.isKey(baseName)
                        scaleFactor = app.DataManager.SignalScaling(baseName);
                        signalData = signalData * scaleFactor;
                    end

                    % Sort by time if necessary
                    if ~issorted(timeData)
                        [timeData, sortIdx] = sort(timeData);
                        signalData = signalData(sortIdx);
                    end

                    % Create timeseries with proper properties
                    ts = timeseries(signalData, timeData);
                    ts.Name = baseName;  % Ensure char for compatibility
                    ts.DataInfo.Units = '';    % Add units if available

                    % Use addToRun for better control
                    try
                        % Basic addToRun call without name-value pairs for compatibility
                        sigID = Simulink.sdi.addToRun(runID, 'vars', ts);

                        if sigID > 0
                            success = true;
                            fprintf('    ✓ Added signal: %s (ID: %d)\n', fullName, sigID);
                        else
                            fprintf('  Warning: Failed to add signal %s to SDI\n', fullName);
                        end

                    catch addError
                        fprintf('  Error adding signal %s: %s\n', fullName, addError.message);
                    end

                catch ME
                    fprintf('  Error processing signal %s: %s\n', fullName, ME.message);
                end
            end
        end


        % function traverse(node, prefix)
        %     % If it's a leaf node (signal)
        %     if isempty(node.Children)
        %         sigName = node.Text;
        %         fullName = strjoin([prefix, sigName], '/');
        %
        %         if isKey(app.DataManager.SignalDataMap, sigName)
        %             signalStruct = app.DataManager.SignalDataMap(sigName);
        %             t = signalStruct.Time;
        %             y = signalStruct.Data;
        %
        %             ts = timeseries(y, t, 'Name', fullName);
        %             tsList{end+1} = ts;
        %             nameList{end+1} = fullName;
        %         end
        %     else
        %         for k = 1:numel(node.Children)
        %             traverse(node.Children(k), [prefix, node.Text]);
        %         end
        %     end
        % end

        function createReportPDF(obj, scope, options)
            app = obj.App;

            % Get save location
            defaultName = sprintf('%s_%s.pdf', strrep(app.PDFReportTitle, ' ', '_'), datestr(now, 'yyyymmdd'));
            [file, path] = uiputfile('*.pdf', 'Save PDF Report', defaultName);
            if isequal(file, 0)
                app.restoreFocus();
                return;
            end

            fullPath = fullfile(path, file);

            try
                app.StatusLabel.Text = '📄 Generating PDF report...';
                app.StatusLabel.FontColor = [0.2 0.6 0.9];
                drawnow;

                % Determine which plots to include
                plotsToInclude = obj.determinePlotsToInclude(scope);

                if isempty(plotsToInclude)
                    app.StatusLabel.Text = '⚠️ No plots to include in PDF';
                    app.StatusLabel.FontColor = [0.9 0.6 0.2];
                    return;
                end


                % Create temporary figure for report generation
                reportFig = figure('Visible', 'off', 'Position', [100 100 800 600], ...
                    'Color', [1 1 1], 'PaperType', 'a4', 'PaperOrientation', 'portrait');

                % Generate report
                obj.generatePDFReport(reportFig, plotsToInclude, options, fullPath);

                % Clean up
                close(reportFig);

                % Check if file was created
                if exist(fullPath, 'file')
                    app.StatusLabel.Text = sprintf('✅ PDF report saved: %s', file);
                    app.StatusLabel.FontColor = [0.2 0.6 0.9];

                    % Ask if user wants to open the PDF
                    answer = questdlg('PDF created successfully. Open it now?', 'PDF Export', 'Yes', 'No', 'Yes');
                    if strcmp(answer, 'Yes')
                        try
                            if ispc
                                winopen(fullPath);
                            elseif ismac
                                system(['open "' fullPath '"']);
                            else
                                system(['xdg-open "' fullPath '"']);
                            end
                        catch
                            fprintf('Could not open PDF automatically\n');
                        end
                    end
                else
                    app.StatusLabel.Text = '❌ PDF file was not created';
                    app.StatusLabel.FontColor = [0.9 0.3 0.3];
                end

            catch ME
                if exist('reportFig', 'var') && isvalid(reportFig)
                    close(reportFig);
                end
                app.StatusLabel.Text = ['❌ PDF generation failed: ' ME.message];
                app.StatusLabel.FontColor = [0.9 0.3 0.3];
                fprintf('Debug: Error during PDF generation: %s\n', ME.message);
                fprintf('Debug: Stack trace:\n');
                for i = 1:length(ME.stack)
                    fprintf('  %s (line %d)\n', ME.stack(i).name, ME.stack(i).line);
                end
            end

            app.restoreFocus();
        end

        function generatePDFReport(obj, reportFig, plotsToInclude, options, outputPath)
            app = obj.App;

            try
                % Simple approach: Create one large figure with all content
                totalPlots = size(plotsToInclude, 1);

                % Create a very tall figure to accommodate all pages
                figHeight = 600 + (totalPlots * 400); % Title space + plots
                set(reportFig, 'Position', [100 100 800 figHeight]);

                clf(reportFig);

                % Create title section at the top
                titleAx = axes('Parent', reportFig, 'Position', [0.05 0.85 0.9 0.1], 'Visible', 'off');
                obj.createTitlePageContent(titleAx, options);

                % Create each plot in its own section
                figureNumber = 1;
                plotSpacing = 0.8 / totalPlots; % Divide remaining 80% of figure among plots

                for i = 1:totalPlots
                    tabIdx = plotsToInclude(i, 1);
                    subplotIdx = plotsToInclude(i, 2);

                    % Calculate position for this plot
                    yTop = 0.8 - (i-1) * plotSpacing;
                    yBottom = yTop - plotSpacing * 0.9; % Leave some space between plots
                    plotHeight = plotSpacing * 0.6; % 60% for plot
                    captionHeight = plotSpacing * 0.3; % 30% for caption

                    % Create plot area
                    plotAx = axes('Parent', reportFig, 'Position', [0.1 yBottom + captionHeight, 0.8 plotHeight]);

                    % Get source data and plot
                    if tabIdx <= numel(obj.AxesArrays) && subplotIdx <= numel(obj.AxesArrays{tabIdx})
                        sourceAx = obj.AxesArrays{tabIdx}(subplotIdx);
                        if isvalid(sourceAx)
                            obj.copyPlotContent(sourceAx, plotAx);

                            % *** NEW: Add subplot title to the plot itself ***
                            subplotTitle = obj.getSubplotTitle(app, tabIdx, subplotIdx);
                            if obj.containsHebrew(subplotTitle)
                                processedTitle = obj.processHebrewText(subplotTitle);
                            else
                                processedTitle = subplotTitle;
                            end

                            title(plotAx, processedTitle, 'FontSize', 14, 'FontWeight', 'bold');
                        end
                    end

                    % Add caption below plot
                    captionAx = axes('Parent', reportFig, 'Position', [0.1 yBottom 0.8 captionHeight], 'Visible', 'off');
                    obj.addCaptionContent(captionAx, tabIdx, subplotIdx, figureNumber);

                    figureNumber = figureNumber + 1;

                    % Update progress
                    app.StatusLabel.Text = sprintf('📄 Adding figure %d of %d...', figureNumber-1, totalPlots);
                    drawnow;
                end

                % Print the entire figure as one PDF
                print(reportFig, outputPath, '-dpdf', '-fillpage');

                % Reset figure size
                set(reportFig, 'Position', [100 100 800 600]);

                app.StatusLabel.Text = sprintf('✅ Created single PDF with title + %d figures', totalPlots);

            catch ME
                % Reset figure size in case of error
                try
                    set(reportFig, 'Position', [100 100 800 600]);
                catch
                end
                error('PDF generation failed: %s', ME.message);
            end
        end
        function enableDataTipsMode(obj, ax)
            % Enable data tips mode - user can click data points, right-click to exit
            try
                % Enable datacursor mode
                fig = ancestor(ax, 'figure');
                dcm = datacursormode(fig);
                dcm.Enable = 'on';
                dcm.DisplayStyle = 'datatip';
                dcm.SnapToDataVertex = 'on';
                dcm.UpdateFcn = @(obj_dcm, event_obj) obj.customDataTipText(obj_dcm, event_obj);

                % Update axes interactions
                ax.Interactions = [dataTipInteraction];

                % Show instructions
                obj.App.StatusLabel.Text = '🎯 Data Tips Mode: Click data points for info, right-click to exit';
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

                % Create exit context menu for data tips mode
                exitCm = uicontextmenu(obj.App.UIFigure);
                uimenu(exitCm, 'Text', '❌ Exit Data Tips Mode', ...
                    'MenuSelectedFcn', @(src, event) obj.exitDataTipsMode(ax));

                % Temporarily replace context menu
                ax.UserData.OriginalContextMenu = ax.ContextMenu;
                ax.ContextMenu = exitCm;

            catch ME
                obj.App.StatusLabel.Text = '❌ Error enabling data tips mode';
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end


        function createTitlePageContent(obj, ax, ~)
            app = obj.App;

            axis(ax, 'off');

            % Process Hebrew text
            processedTitle = obj.processHebrewText(app.PDFReportTitle);
            processedAuthor = obj.processHebrewText(app.PDFReportAuthor);

            % Check if title is Hebrew
            titleIsHebrew = obj.containsHebrew(app.PDFReportTitle);
            authorIsHebrew = obj.containsHebrew(app.PDFReportAuthor);

            % Title - adjust alignment based on language
            if titleIsHebrew
                text(ax, 0.95, 0.8, processedTitle, 'FontSize', 18, 'FontWeight', 'bold', ...
                    'HorizontalAlignment', 'right', 'Units', 'normalized');
            else
                text(ax, 0.5, 0.8, app.PDFReportTitle, 'FontSize', 18, 'FontWeight', 'bold', ...
                    'HorizontalAlignment', 'center', 'Units', 'normalized');
            end

            % Author - adjust alignment based on language
            if ~isempty(app.PDFReportAuthor)
                if authorIsHebrew
                    text(ax, 0.95, 0.5, ['Author: ' processedAuthor], 'FontSize', 12, ...
                        'HorizontalAlignment', 'right', 'Units', 'normalized');
                else
                    text(ax, 0.5, 0.5, ['Author: ' app.PDFReportAuthor], 'FontSize', 12, ...
                        'HorizontalAlignment', 'center', 'Units', 'normalized');
                end
            end

            % Date (always center)
            text(ax, 0.5, 0.2, ['Generated: ' datestr(now, 'yyyy-mm-dd HH:MM')], ...
                'FontSize', 10, 'HorizontalAlignment', 'center', 'Units', 'normalized');
        end

        function addCaptionContent(obj, captionAx, tabIdx, subplotIdx, figureNumber)
            app = obj.App;

            % Get caption and description
            caption = '';
            description = '';

            if numel(app.SubplotCaptions) >= tabIdx && ...
                    numel(app.SubplotCaptions{tabIdx}) >= subplotIdx && ...
                    ~isempty(app.SubplotCaptions{tabIdx}{subplotIdx})
                caption = app.SubplotCaptions{tabIdx}{subplotIdx};
            end

            if numel(app.SubplotDescriptions) >= tabIdx && ...
                    numel(app.SubplotDescriptions{tabIdx}) >= subplotIdx && ...
                    ~isempty(app.SubplotDescriptions{tabIdx}{subplotIdx})
                description = app.SubplotDescriptions{tabIdx}{subplotIdx};
            end

            % Default values if empty
            if isempty(caption)
                caption = sprintf('Caption for subplot %d', subplotIdx);
            end
            if isempty(description)
                description = 'No description provided.';
            end

            % Check if text is Hebrew and process accordingly
            captionIsHebrew = obj.containsHebrew(caption);
            descriptionIsHebrew = obj.containsHebrew(description);

            % *** FIX: Handle figure label and caption properly ***
            figureLabel = app.PDFFigureLabel; % 'Figure' or 'איור'

            if strcmp(figureLabel, 'איור')
                % Hebrew label: Build Hebrew-style sentence and process as Hebrew
                % Format: "איור 1: שתיים" (not reversed parts)
                fullCaptionText = sprintf('איור %d: %s', figureNumber, caption);
                processedCaptionText = obj.processHebrewText(fullCaptionText);
                labelAlign = 'right';
                labelX = 0.95;
            else
                % English label: Build English-style sentence
                if captionIsHebrew
                    % English label but Hebrew caption
                    processedCaption = obj.processHebrewText(caption);
                    fullCaptionText = sprintf('%s %d: %s', figureLabel, figureNumber, processedCaption);
                    labelAlign = 'right';  % Right align because caption is Hebrew
                    labelX = 0.95;
                else
                    % Both English
                    fullCaptionText = sprintf('%s %d: %s', figureLabel, figureNumber, caption);
                    labelAlign = 'left';
                    labelX = 0.05;
                end
                processedCaptionText = fullCaptionText;
            end

            % Process description
            if descriptionIsHebrew
                processedDescription = obj.processHebrewText(description);
                descAlign = 'right';
                descX = 0.95;
            else
                processedDescription = description;
                descAlign = 'left';
                descX = 0.05;
            end

            % Add figure label and caption
            text(captionAx, labelX, 0.8, processedCaptionText, ...
                'FontSize', 10, 'FontWeight', 'bold', 'Units', 'normalized', ...
                'VerticalAlignment', 'top', 'Interpreter', 'none', ...
                'HorizontalAlignment', labelAlign);

            % Add description
            text(captionAx, descX, 0.5, processedDescription, ...
                'FontSize', 9, 'Units', 'normalized', ...
                'VerticalAlignment', 'top', 'Interpreter', 'none', ...
                'HorizontalAlignment', descAlign);
        end
        function exitDataTipsMode(obj, ax)
            % Exit data tips mode and restore normal context menu
            try
                % Disable datacursor mode
                fig = ancestor(ax, 'figure');
                dcm = datacursormode(fig);
                dcm.Enable = 'off';

                % Restore normal interactions
                ax.Interactions = [panInteraction, zoomInteraction];

                % Restore original context menu
                if isstruct(ax.UserData) && isfield(ax.UserData, 'OriginalContextMenu')
                    ax.ContextMenu = ax.UserData.OriginalContextMenu;
                    ax.UserData = rmfield(ax.UserData, 'OriginalContextMenu');
                end

                obj.App.StatusLabel.Text = '✅ Exited data tips mode';
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];

            catch ME
                obj.App.StatusLabel.Text = '❌ Error exiting data tips mode';
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end

        % Enable synchronized zoom/pan (per-tab linking approach)
        function enableSyncZoom(obj)
            % Enable linking for all tabs (legacy function - now uses per-tab approach)
            for i = 1:numel(obj.AxesArrays)
                % Ensure arrays are large enough
                while length(obj.TabLinkedAxes) < i
                    obj.TabLinkedAxes(end+1) = false;
                    obj.TabLinkedAxesObjects{end+1} = [];
                end

                % Enable linking for this tab
                obj.TabLinkedAxes(i) = true;
                obj.linkTabAxes(i);

                % Update the UI toggle if it exists
                if i <= length(obj.TabControls) && ~isempty(obj.TabControls{i}) && ...
                        isfield(obj.TabControls{i}, 'LinkAxesToggle')
                    obj.TabControls{i}.LinkAxesToggle.Value = true;
                end
            end
        end

        function addTabControls(obj, tabIdx)
            % Add layout and subplot controls in row 1 of the main layout
            mainLayout = obj.MainTabGridLayouts{tabIdx};

            % Create control panel in row 1 of the main layout
            controlPanel = uipanel(mainLayout);
            controlPanel.Layout.Row = 1;
            controlPanel.Layout.Column = 1;

            % Get current layout for this tab
            currentLayout = obj.TabLayouts{tabIdx};
            currentRows = currentLayout(1);
            currentCols = currentLayout(2);

            % Layout controls within the panel
            controlY = 20;

            uilabel(controlPanel, 'Text', 'Rows:', ...
                'Position', [20 controlY 50 25], ...
                'FontWeight', 'bold', 'FontSize', 11);

            rowsSpinner = uispinner(controlPanel, ...
                'Position', [75 controlY 60 25], ...
                'Limits', [1 10], 'Value', currentRows, 'FontSize', 10, ...
                'ValueChangedFcn', @(src, event) obj.onTabLayoutChanged(tabIdx, src.Value, []));

            uilabel(controlPanel, 'Text', 'Cols:', ...
                'Position', [150 controlY 50 25], ...
                'FontWeight', 'bold', 'FontSize', 11);

            colsSpinner = uispinner(controlPanel, ...
                'Position', [205 controlY 60 25], ...
                'Limits', [1 10], 'Value', currentCols, 'FontSize', 10, ...
                'ValueChangedFcn', @(src, event) obj.onTabLayoutChanged(tabIdx, [], src.Value));

            % Subplot selection
            uilabel(controlPanel, 'Text', 'Current Subplot:', ...
                'Position', [290 controlY 100 25], ...
                'FontWeight', 'bold', 'FontSize', 11);

            % Calculate subplot options
            nPlots = currentRows * currentCols;
            plotItems = cell(nPlots, 1);
            for i = 1:nPlots
                plotItems{i} = sprintf('Plot %d', i);
            end

            % Ensure SelectedSubplotIdx is valid for this tab
            validSubplotIdx = obj.SelectedSubplotIdx;
            if validSubplotIdx > nPlots
                validSubplotIdx = 1;
                obj.SelectedSubplotIdx = 1;
            end

            subplotDropdown = uidropdown(controlPanel, ...
                'Position', [400 controlY 120 25], ...
                'Items', plotItems, ...
                'Value', sprintf('Plot %d', validSubplotIdx), ...
                'FontSize', 10, ...
                'ValueChangedFcn', @(src, event) obj.onSubplotSelected(tabIdx, src.Value));

            % *** CRITICAL FIX: Use dynamic tab finding instead of static tabIdx ***
            linkAxesToggle = uibutton(controlPanel, 'state', ...
                'Position', [530 controlY 100 25], ...
                'Text', 'Link Tab Axes', ...
                'FontSize', 9, ...
                'Tooltip', 'Link X-axes of all subplots in this tab only', ...
                'ValueChangedFcn', @(src, event) obj.onTabLinkAxesToggleDynamic(src, event));

            % Set initial state
            if tabIdx <= length(obj.TabLinkedAxes)
                linkAxesToggle.Value = obj.TabLinkedAxes(tabIdx);
            else
                linkAxesToggle.Value = false;
            end

            % Store references to update them later
            obj.TabControls{tabIdx} = struct(...
                'Panel', controlPanel, ...
                'RowsSpinner', rowsSpinner, ...
                'ColsSpinner', colsSpinner, ...
                'SubplotDropdown', subplotDropdown, ...
                'LinkAxesToggle', linkAxesToggle);
        end

        function onTabLinkAxesToggleDynamic(obj, src, event)
            % Find which tab this toggle belongs to by searching through TabControls
            actualTabIdx = obj.findTabIndexFromControl(src);

            if actualTabIdx > 0
                % Call the original method with the CORRECT tab index
                obj.onTabLinkAxesToggle(actualTabIdx, src.Value);
            else
                % Fallback: use current tab
                obj.onTabLinkAxesToggle(obj.CurrentTabIdx, src.Value);
            end
        end

        % FIX 3: Add helper method to find correct tab index

        function tabIdx = findTabIndexFromControl(obj, control)
            % Find which tab contains the given control
            tabIdx = 0;

            for i = 1:numel(obj.TabControls)
                if ~isempty(obj.TabControls{i}) && ...
                        isfield(obj.TabControls{i}, 'LinkAxesToggle') && ...
                        obj.TabControls{i}.LinkAxesToggle == control
                    tabIdx = i;
                    return;
                end
            end
        end
        % Disable synchronized zoom/pan (unlink x-limits of all axes)
        function disableSyncZoom(obj)
            % Disable linking for all tabs (legacy function - now uses per-tab approach)
            for i = 1:length(obj.TabLinkedAxes)
                if obj.TabLinkedAxes(i)
                    obj.TabLinkedAxes(i) = false;
                    obj.unlinkTabAxes(i);

                    % Update the UI toggle if it exists
                    if i <= length(obj.TabControls) && ~isempty(obj.TabControls{i}) && ...
                            isfield(obj.TabControls{i}, 'LinkAxesToggle')
                        obj.TabControls{i}.LinkAxesToggle.Value = false;
                    end
                end
            end
        end

        % New per-tab axis linking functions
        function onTabLinkAxesToggle(obj, tabIdx, isLinked)
            % Handle tab-specific axis linking toggle

            % Ensure arrays are large enough
            while length(obj.TabLinkedAxes) < tabIdx
                obj.TabLinkedAxes(end+1) = false;
                obj.TabLinkedAxesObjects{end+1} = [];
            end

            % Update state
            obj.TabLinkedAxes(tabIdx) = isLinked;

            if isLinked
                obj.linkTabAxes(tabIdx);
            else
                obj.unlinkTabAxes(tabIdx);
            end

            % Update status
            if isLinked
                obj.App.StatusLabel.Text = sprintf('🔗 Linked axes for Tab %d', tabIdx);
                obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
            else
                obj.App.StatusLabel.Text = sprintf('🔓 Unlinked axes for Tab %d', tabIdx);
                obj.App.StatusLabel.FontColor = [0.6 0.6 0.6];
            end
        end

        function linkTabAxes(obj, tabIdx)
            % Link all axes within a specific tab only
            if tabIdx > numel(obj.AxesArrays) || isempty(obj.AxesArrays{tabIdx})
                return;
            end

            % Group axes by their X-axis signal for linking
            % Only link axes that share the same X-axis signal
            xAxisGroups = containers.Map('KeyType', 'char', 'ValueType', 'any');

            for j = 1:numel(obj.AxesArrays{tabIdx})
                ax = obj.AxesArrays{tabIdx}(j);
                if isvalid(ax) && isgraphics(ax)
                    % Get the X-axis signal for this subplot
                    xAxisSignal = 'Time'; % default
                    if size(obj.XAxisSignals, 1) >= tabIdx && size(obj.XAxisSignals, 2) >= j
                        if ischar(obj.XAxisSignals{tabIdx, j}) && ~isempty(obj.XAxisSignals{tabIdx, j})
                            xAxisSignal = obj.XAxisSignals{tabIdx, j};
                        end
                    end

                    % Group axes by their X-axis signal
                    if isKey(xAxisGroups, xAxisSignal)
                        axGroup = xAxisGroups(xAxisSignal);
                        axGroup{end+1} = ax;
                        xAxisGroups(xAxisSignal) = axGroup;
                    else
                        xAxisGroups(xAxisSignal) = {ax};
                    end
                end
            end

            % Link axes within each X-axis group
            allLinkedAxes = [];
            xAxisKeys = keys(xAxisGroups);
            for k = 1:length(xAxisKeys)
                axGroup = xAxisGroups(xAxisKeys{k});
                if length(axGroup) > 1
                    % Convert cell array to array of axes
                    axesToLink = [axGroup{:}];
                    linkaxes(axesToLink, 'x');
                    allLinkedAxes = [allLinkedAxes, axesToLink];
                end
            end

            % Store all linked axes for this tab
            obj.TabLinkedAxesObjects{tabIdx} = allLinkedAxes;
        end

        function unlinkTabAxes(obj, tabIdx)
            % Unlink all axes within a specific tab
            if tabIdx > numel(obj.TabLinkedAxesObjects) || isempty(obj.TabLinkedAxesObjects{tabIdx})
                return;
            end

            % Unlink the previously linked axes in this tab
            linkedAxes = obj.TabLinkedAxesObjects{tabIdx};
            if ~isempty(linkedAxes)
                for i = 1:length(linkedAxes)
                    if isvalid(linkedAxes(i))
                        linkaxes(linkedAxes(i), 'off');
                    end
                end
            end

            % Clear the linked axes list for this tab
            obj.TabLinkedAxesObjects{tabIdx} = [];
        end

        function updateTabLinkAxes(obj, tabIdx)
            % Update axis linking for a tab after subplot changes
            if tabIdx <= length(obj.TabLinkedAxes) && obj.TabLinkedAxes(tabIdx)
                obj.linkTabAxes(tabIdx);
            end
        end
        function setupTabCallbacks(obj)
            % Set up callbacks for tab selection to handle + tab clicks
            obj.App.MainTabGroup.SelectionChangedFcn = @(src, event) obj.onTabSelectionChanged(event);
        end
        function updateSignalTreeForTabChange(app)
            % Update signal tree when switching tabs
            if ~isempty(app.PlotManager) && isvalid(app.PlotManager)
                app.PlotManager.updateSignalTreeForCurrentTab();
            end
        end
        function addNewTabFromPlus(obj)
            % Simply call the regular addNewTab method
            obj.addNewTab();
        end

        function onTabSelectionChanged(obj, event)
            % Handle tab selection changes, including + tab clicks
            selectedTab = event.NewValue;

            % Check if the selected tab is the + tab
            if strcmp(selectedTab.Title, '+')
                % Create a new tab instead of staying on the + tab
                obj.addNewTabFromPlus();
            else
                % Update current tab index for regular tabs
                tabIdx = find(cellfun(@(t) t == selectedTab, obj.PlotTabs));
                if ~isempty(tabIdx)
                    % Make sure we're not counting the + tab
                    plusTabIdx = find(cellfun(@(t) strcmp(t.Title, '+'), obj.PlotTabs));
                    if ~isempty(plusTabIdx) && tabIdx == plusTabIdx
                        return; % Don't set current tab to + tab
                    end

                    % Only proceed if we're actually switching to a different tab
                    if obj.CurrentTabIdx == tabIdx
                        return; % Already on this tab, no need to do anything
                    end

                    % Store previous tab for cleanup
                    previousTabIdx = obj.CurrentTabIdx;

                    % Update current tab index FIRST (minimal operation)
                    obj.CurrentTabIdx = tabIdx;

                    % Defer expensive operations using timer for smooth switching
                    if ~isempty(obj.TabSwitchTimer) && isvalid(obj.TabSwitchTimer)
                        stop(obj.TabSwitchTimer);
                        delete(obj.TabSwitchTimer);
                    end

                    % Create timer to handle UI updates after tab is visually switched
                    obj.TabSwitchTimer = timer('ExecutionMode', 'singleShot', ...
                        'StartDelay', 0.001, ... % Very short delay
                        'TimerFcn', @(~,~) obj.finishTabSwitch(previousTabIdx));
                    start(obj.TabSwitchTimer);
                end
            end
        end

        function finishTabSwitch(obj, previousTabIdx)
            % Complete the tab switch operations after visual transition
            try
                % Clear highlights from previous tab (if valid)
                if previousTabIdx > 0 && previousTabIdx <= numel(obj.AxesArrays)
                    obj.App.clearSubplotHighlights(previousTabIdx);
                end

                % Update signal tree indicators only (don't rebuild entire tree)
                obj.updateSignalTreeIndicatorsOnly();

                % Highlight current subplot in the new tab
                obj.App.highlightSelectedSubplot(obj.CurrentTabIdx, obj.SelectedSubplotIdx);

                % Clean up timer
                if ~isempty(obj.TabSwitchTimer) && isvalid(obj.TabSwitchTimer)
                    delete(obj.TabSwitchTimer);
                    obj.TabSwitchTimer = [];
                end
            catch ME
                fprintf('Error in finishTabSwitch: %s\n', ME.message);
            end
        end

        function updateSignalTreeIndicatorsOnly(obj)
            % Lightweight update of signal tree indicators without rebuilding the tree
            tabIdx = obj.CurrentTabIdx;
            subplotIdx = obj.SelectedSubplotIdx;

            % Get assigned signals for current subplot
            assignedSignals = {};
            if tabIdx <= numel(obj.AssignedSignals) && ...
                    subplotIdx <= numel(obj.AssignedSignals{tabIdx})
                assignedSignals = obj.AssignedSignals{tabIdx}{subplotIdx};
            end

            % Update visual indicators (lightweight operation)
            obj.updateSignalTreeVisualIndicators(assignedSignals);

            % Update the signal properties table
            if ismethod(obj.App, 'updateSignalPropsTable')
                obj.App.updateSignalPropsTable(assignedSignals);
            end
        end



        function toggleDataTipsForAxes(obj, ax)
            % Toggle data tips while preserving the context menu
            try
                % Check if data tips are currently enabled by looking at datacursormode
                fig = ancestor(ax, 'figure');
                dcm = datacursormode(fig);

                if strcmp(dcm.Enable, 'on')
                    % Data tips are ON - turn them OFF
                    dcm.Enable = 'off';
                    ax.Interactions = [panInteraction, zoomInteraction];
                    obj.App.StatusLabel.Text = '🎯 Data tips disabled - right-click for options';
                    obj.App.StatusLabel.FontColor = [0.5 0.5 0.5];
                else
                    % Data tips are OFF - turn them ON but keep context menu
                    dcm.Enable = 'on';
                    dcm.DisplayStyle = 'datatip';
                    dcm.SnapToDataVertex = 'on';
                    dcm.UpdateFcn = @(obj_dcm, event_obj) obj.customDataTipText(obj_dcm, event_obj);

                    % Set interactions to include data tips
                    ax.Interactions = [dataTipInteraction, panInteraction, zoomInteraction];

                    obj.App.StatusLabel.Text = '🎯 Data tips enabled - left-click data points, right-click for menu';
                    obj.App.StatusLabel.FontColor = [0.2 0.6 0.9];
                end

            catch ME
                obj.App.StatusLabel.Text = sprintf('❌ Error toggling data tips: %s', ME.message);
                obj.App.StatusLabel.FontColor = [0.9 0.3 0.3];
            end
        end
        function plotsToInclude = determinePlotsToInclude(obj, scope)
            plotsToInclude = [];

            switch scope
                case 'currentTab'
                    tabIdx = obj.CurrentTabIdx;
                    if tabIdx <= numel(obj.AxesArrays) && ~isempty(obj.AxesArrays{tabIdx})
                        for i = 1:numel(obj.AxesArrays{tabIdx})
                            plotsToInclude(end+1,:) = [tabIdx, i];
                        end
                    end

                case 'allTabs'
                    for tabIdx = 1:numel(obj.AxesArrays)
                        if ~isempty(obj.AxesArrays{tabIdx})
                            for i = 1:numel(obj.AxesArrays{tabIdx})
                                plotsToInclude(end+1,:) = [tabIdx, i];
                            end
                        end
                    end

                case 'currentTabActive'
                    tabIdx = obj.CurrentTabIdx;
                    if tabIdx <= numel(obj.AssignedSignals)
                        for i = 1:numel(obj.AssignedSignals{tabIdx})
                            if ~isempty(obj.AssignedSignals{tabIdx}{i})
                                plotsToInclude(end+1,:) = [tabIdx, i];
                            end
                        end
                    end

                case 'allTabsActive'
                    for tabIdx = 1:numel(obj.AssignedSignals)
                        for i = 1:numel(obj.AssignedSignals{tabIdx})
                            if ~isempty(obj.AssignedSignals{tabIdx}{i})
                                plotsToInclude(end+1,:) = [tabIdx, i];
                            end
                        end
                    end
            end
        end

        function createTitlePage(obj, fig, ~)
            app = obj.App;

            % Create title page layout
            ax = axes('Parent', fig, 'Position', [0.1 0.1 0.8 0.8], 'Visible', 'off');

            % Title
            text(ax, 0.5, 0.8, app.PDFReportTitle, 'FontSize', 24, 'FontWeight', 'bold', ...
                'HorizontalAlignment', 'center', 'Units', 'normalized');

            % Author
            if ~isempty(app.PDFReportAuthor)
                text(ax, 0.5, 0.7, ['Author: ' app.PDFReportAuthor], 'FontSize', 14, ...
                    'HorizontalAlignment', 'center', 'Units', 'normalized');
            end

            % Date
            text(ax, 0.5, 0.6, ['Generated: ' datestr(now, 'yyyy-mm-dd HH:MM')], ...
                'FontSize', 12, 'HorizontalAlignment', 'center', 'Units', 'normalized');

            % Summary info
            numTabs = numel(obj.AxesArrays);
            totalPlots = 0;
            for i = 1:numTabs
                if ~isempty(obj.AxesArrays{i})
                    totalPlots = totalPlots + numel(obj.AxesArrays{i});
                end
            end

            summaryText = sprintf('Report contains %d tabs with %d total plots', numTabs, totalPlots);
            text(ax, 0.5, 0.4, summaryText, 'FontSize', 12, ...
                'HorizontalAlignment', 'center', 'Units', 'normalized');
        end

        function createPlotPage(obj, fig, tabIdx, subplotIdx, figureNumber, ~)
            app = obj.App;

            % Get source axes
            if tabIdx > numel(obj.AxesArrays) || subplotIdx > numel(obj.AxesArrays{tabIdx})
                return;
            end

            sourceAx = obj.AxesArrays{tabIdx}(subplotIdx);
            if ~isvalid(sourceAx)
                return;
            end

            % Create main plot area (leave space for caption at bottom)
            plotAx = axes('Parent', fig, 'Position', [0.1 0.35 0.8 0.55]);

            % Copy plot content (excluding highlight borders)
            obj.copyPlotContent(sourceAx, plotAx);

            % Add figure title above the plot
            title(plotAx, sprintf('Figure %d: Tab %d, Plot %d', figureNumber, tabIdx, subplotIdx), ...
                'FontSize', 16, 'FontWeight', 'bold');

            % Add caption and description below the plot
            obj.addCaptionToPage(fig, tabIdx, subplotIdx, figureNumber);
        end





        function copyPlotContent(~, sourceAx, targetAx)
            % Copy plot content excluding highlight borders
            allChildren = allchild(sourceAx);
            validChildren = [];

            % Get highlight borders to exclude
            highlightBorders = [];
            if isstruct(sourceAx.UserData) && isfield(sourceAx.UserData, 'HighlightBorders')
                highlightBorders = sourceAx.UserData.HighlightBorders;
            end

            % Filter children: exclude highlight borders
            for i = 1:numel(allChildren)
                child = allChildren(i);

                % Skip if it's a highlight border
                isHighlightBorder = false;
                for j = 1:numel(highlightBorders)
                    if isequal(child, highlightBorders(j))
                        isHighlightBorder = true;
                        break;
                    end
                end

                if ~isHighlightBorder && isa(child, 'matlab.graphics.chart.primitive.Line')
                    validChildren = [validChildren; child];
                end
            end

            % Copy valid children
            if ~isempty(validChildren)
                copyobj(validChildren, targetAx);
            end

            % Copy axes properties
            targetAx.XLabel.String = sourceAx.XLabel.String;
            targetAx.YLabel.String = sourceAx.YLabel.String;
            % targetAx.XLim = sourceAx.XLim;
            % targetAx.YLim = sourceAx.YLim;

            % Set normal styling
            targetAx.XColor = [0.15 0.15 0.15];
            targetAx.YColor = [0.15 0.15 0.15];
            targetAx.LineWidth = 1;
            grid(targetAx, 'on');

            % Add legend if there are labeled plots
            legendEntries = {};
            for i = 1:numel(targetAx.Children)
                child = targetAx.Children(i);
                if isa(child, 'matlab.graphics.chart.primitive.Line') && ...
                        isprop(child, 'DisplayName') && ~isempty(child.DisplayName)
                    legendEntries{end+1} = child.DisplayName;
                end
            end

            if ~isempty(legendEntries)
                legend(targetAx, legendEntries, 'Location', 'best');
            end
        end





        addCaptionToPage
        % Set crosshair position from mouse click
        function setCrosshairFromClick(obj, ax, ~)
            if ~obj.App.CursorState
                return;
            end

            try
                % Get click position
                mousePos = ax.CurrentPoint;
                newX = mousePos(1, 1);

                % Check if X is within bounds
                xlims = ax.XLim;
                if newX >= xlims(1) && newX <= xlims(2)
                    obj.setCrosshairX(newX);
                end
            catch
                % Ignore errors
            end
        end
        function createPDFFromImages(obj, imageFiles, outputPath)
            % Create a single PDF from multiple images

            if isempty(imageFiles)
                error('No images to convert to PDF');
            end

            % Create a temporary figure for PDF assembly
            pdfFig = figure('Visible', 'off', 'Position', [100 100 800 600], ...
                'Color', [1 1 1], 'PaperType', 'a4', 'PaperOrientation', 'portrait');

            try
                for i = 1:numel(imageFiles)
                    % Clear figure
                    clf(pdfFig);

                    % Read and display the image
                    img = imread(imageFiles{i});

                    % Create axes that fills the entire figure
                    ax = axes('Parent', pdfFig, 'Position', [0 0 1 1]);

                    % Display image
                    imshow(img, 'Parent', ax);
                    axis(ax, 'off');

                    % Print to PDF
                    if i == 1
                        % First page: create new PDF
                        print(pdfFig, outputPath, '-dpdf', '-fillpage', '-r300');
                    else
                        % This is the tricky part - we need to append without using -append
                        % Solution: Use temporary files and system command if available
                        tempPdfFile = [tempname '.pdf'];
                        print(pdfFig, tempPdfFile, '-dpdf', '-fillpage', '-r300');

                        % Try to combine using system tools
                        success = obj.appendPDFPage(outputPath, tempPdfFile);

                        if ~success
                            % Fallback: create individual files
                            [pathStr, name, ext] = fileparts(outputPath);
                            backupFile = fullfile(pathStr, sprintf('%s_page%02d%s', name, i, ext));
                            copyfile(tempPdfFile, backupFile);
                            fprintf('Created backup file: %s\n', backupFile);
                        end

                        % Clean up temp file
                        if exist(tempPdfFile, 'file')
                            delete(tempPdfFile);
                        end
                    end
                end

            catch ME
                if isvalid(pdfFig)
                    close(pdfFig);
                end
                rethrow(ME);
            end

            % Clean up
            close(pdfFig);
        end

        function success = appendPDFPage(~, mainPdfFile, pagePdfFile)
            success = false;

            try
                % Method 1: Try using MATLAB's built-in approach with exportgraphics (R2020a+)
                if exist('exportgraphics', 'file')
                    % This method might work in newer MATLAB versions
                    % For now, we'll use a different approach
                end

                % Method 2: Try system command (if ghostscript is available)
                if ispc
                    % Windows: try using ghostscript if available
                    gsCommand = sprintf('gswin64c -dNOPAUSE -sDEVICE=pdfwrite -sOUTPUTFILE=temp_combined.pdf -dBATCH "%s" "%s"', ...
                        mainPdfFile, pagePdfFile);

                    [status, ~] = system(gsCommand);
                    if status == 0 && exist('temp_combined.pdf', 'file')
                        movefile('temp_combined.pdf', mainPdfFile);
                        success = true;
                        return;
                    end
                end

                % Method 3: Manual approach - read both PDFs and combine
                % This is complex and would require a PDF library

                % For now, we'll return false and let the calling function handle it
                success = false;

            catch
                success = false;
            end
        end


        function hasConflict = checkSignalNameConflictInUITree(obj, signalName, currentTabIdx, currentAxesIdx)
            % Check if the given signal name exists ANYWHERE in the data (assigned or available)
            hasConflict = false;

            % Method 1: Check in all other axes assignments
            for tabIdx = 1:numel(obj.AssignedSignals)
                assignments = obj.AssignedSignals{tabIdx};

                for axesIdx = 1:numel(assignments)
                    % Skip the current axes we're processing
                    if tabIdx == currentTabIdx && axesIdx == currentAxesIdx
                        continue;
                    end

                    % Check all assigned signals in this axes
                    assignedSigs = assignments{axesIdx};
                    for sigIdx = 1:numel(assignedSigs)
                        if strcmp(assignedSigs{sigIdx}.Signal, signalName)
                            hasConflict = true;
                            return;
                        end
                    end
                end
            end

            % Method 2: Check if this signal name exists in multiple CSV files
            % (This ensures suffix even if signal isn't assigned elsewhere yet)
            signalCount = 0;

            % Count occurrences across all CSV files
            if isprop(obj.App, 'DataManager') && ~isempty(obj.App.DataManager.DataTables)
                for csvIdx = 1:numel(obj.App.DataManager.DataTables)
                    T = obj.App.DataManager.DataTables{csvIdx};
                    if ~isempty(T) && ismember(signalName, T.Properties.VariableNames)
                        signalCount = signalCount + 1;
                    end
                end
            end

            % Also check derived signals
            if isprop(obj.App, 'SignalOperations') && ~isempty(obj.App.SignalOperations)
                try
                    derivedSignals = obj.App.SignalOperations.getAllDerivedSignalNames();
                    if any(strcmp(derivedSignals, signalName))
                        signalCount = signalCount + 1;
                    end
                catch
                    % Ignore errors if method doesn't exist
                end
            end

            % If the same signal name exists in more than one source, it needs suffix
            if signalCount > 1
                hasConflict = true;
                return;
            end

            % Method 3: Check the signal tree structure for duplicate names
            % This catches cases where the signal might be available but not yet assigned
            if isprop(obj.App, 'SignalTree') && ~isempty(obj.App.SignalTree)
                try
                    allNodes = obj.App.SignalTree.Children;
                    sourceCount = 0;

                    for i = 1:numel(allNodes)
                        csvNode = allNodes(i);
                        if ~isempty(csvNode.Children)
                            for j = 1:numel(csvNode.Children)
                                sigNode = csvNode.Children(j);
                                if isprop(sigNode, 'NodeData') && ~isempty(sigNode.NodeData)
                                    nodeSignalName = sigNode.NodeData.Signal;
                                    if strcmp(nodeSignalName, signalName)
                                        sourceCount = sourceCount + 1;
                                    end
                                end
                            end
                        end
                    end

                    if sourceCount > 1
                        hasConflict = true;
                        return;
                    end
                catch
                    % Ignore errors if signal tree structure is different
                end
            end
        end

        function subplotTitle = getSubplotTitle(~, app, tabIdx, subplotIdx)
            % Get subplot title, with fallback to default
            subplotTitle = '';

            if numel(app.SubplotTitles) >= tabIdx && ...
                    numel(app.SubplotTitles{tabIdx}) >= subplotIdx && ...
                    ~isempty(app.SubplotTitles{tabIdx}{subplotIdx})
                subplotTitle = app.SubplotTitles{tabIdx}{subplotIdx};
            end

            % Default if empty
            if isempty(subplotTitle)
                subplotTitle = sprintf('Subplot %d', subplotIdx);
            end
        end

        % Custom data tip text function (like SDI)
        function txt = customDataTipText(~, ~, event_obj)
            % Get position and target
            pos = get(event_obj, 'Position');
            target = get(event_obj, 'Target');

            % Get signal name from DisplayName
            signalName = get(target, 'DisplayName');
            if isempty(signalName)
                signalName = 'Signal';
            end

            % Format like SDI: Signal name, Time, Value
            txt = {
                ['Signal: ' signalName], ...
                ['Time: ' num2str(pos(1), '%.6f')], ...
                ['Value: ' num2str(pos(2), '%.6f')]
                };

            % Add index if available
            try
                % Find the closest data point index
                xdata = get(target, 'XData');
                ydata = get(target, 'YData');

                if ~isempty(xdata) && ~isempty(ydata)
                    [~, idx] = min(abs(xdata - pos(1)));
                    txt{end+1} = ['Index: ' num2str(idx)];
                end
            catch
                % Skip index if can't determine
            end
        end
        % New method to update visual indicators in signal tree
        function updateSignalTreeVisualIndicators(obj, assignedSignals)
            % Update checkmarks in signal tree based on assigned signals
            allNodes = obj.App.SignalTree.Children;
            selectedNodes = [];

            for i = 1:numel(allNodes)
                csvNode = allNodes(i);
                for j = 1:numel(csvNode.Children)
                    sigNode = csvNode.Children(j);
                    isAssigned = false;

                    % Check if this signal is assigned to current subplot
                    for k = 1:numel(assignedSignals)
                        if isequal(sigNode.NodeData, assignedSignals{k})
                            isAssigned = true;
                            selectedNodes = [selectedNodes sigNode];
                            break;
                        end
                    end

                    % Update visual indicator
                    if isAssigned
                        % Add checkmark if not already present
                        if ~startsWith(sigNode.Text, '✔ ')
                            sigNode.Text = sprintf('✔ %s', strrep(sigNode.Text, '✔ ', ''));
                        end
                    else
                        % Remove checkmark if present
                        if startsWith(sigNode.Text, '✔ ')
                            sigNode.Text = strrep(sigNode.Text, '✔ ', '');
                        end
                    end
                end
            end

            % Select the assigned signal nodes in the tree
            obj.App.SignalTree.SelectedNodes = selectedNodes;
        end

        function processedText = processHebrewText(obj, text)
            % Fix Hebrew display in MATLAB by reversing text properly

            if isempty(text)
                processedText = text;
                return;
            end

            % If text doesn't contain Hebrew, return as-is
            if ~obj.containsHebrew(text)
                processedText = text;
                return;
            end

            % For text containing Hebrew, reverse the entire string.
            % This handles mixed Hebrew-English text and Hebrew-only text.
            processedText = fliplr(text);

            % Debug output to see what's happening
            % fprintf('Original: "%s" -> Processed: "%s"\n', text, processedText);
        end

        function ensureAssignedSignalsMatchLayout(obj, tabIdx)
            % Ensure AssignedSignals array matches the current tab layout
            if tabIdx > numel(obj.TabLayouts) || tabIdx > numel(obj.AssignedSignals)
                return;
            end

            layout = obj.TabLayouts{tabIdx};
            expectedSubplots = layout(1) * layout(2);

            % Check if AssignedSignals matches the layout
            if numel(obj.AssignedSignals{tabIdx}) ~= expectedSubplots
                % Resize AssignedSignals to match layout
                oldAssignments = obj.AssignedSignals{tabIdx};
                obj.AssignedSignals{tabIdx} = cell(expectedSubplots, 1);

                % Copy old assignments up to the limit
                for i = 1:min(numel(oldAssignments), expectedSubplots)
                    obj.AssignedSignals{tabIdx}{i} = oldAssignments{i};
                end

                % Initialize remaining cells
                for i = (numel(oldAssignments)+1):expectedSubplots
                    obj.AssignedSignals{tabIdx}{i} = {};
                end
            end

            % Reset subplot index if it's out of bounds
            if obj.SelectedSubplotIdx > expectedSubplots
                obj.SelectedSubplotIdx = 1;

                % Update app's dropdown if it exists
                obj.App.PlotManager.updateTabSubplotDropdown(tabIdx);
            end
        end

    
        function addedCount = addSignalsToSubplot(obj, tabIdx, subplotIdx, signalsToAdd)
            % PlotManager method to safely add signals to a subplot
            % RETURNS the number of signals actually added

            % Ensure layout consistency first
            obj.ensureAssignedSignalsMatchLayout(tabIdx);

            % Validate subplot index
            if subplotIdx > numel(obj.AssignedSignals{tabIdx})
                fprintf('Warning: Subplot index %d exceeds available subplots (%d)\n', ...
                    subplotIdx, numel(obj.AssignedSignals{tabIdx}));
                addedCount = 0;  % RETURN 0 instead of just return
                return;
            end

            % Get current assignments safely
            currentAssignments = obj.AssignedSignals{tabIdx}{subplotIdx};
            if isempty(currentAssignments)
                currentAssignments = {};
            end

            % Add signals
            addedCount = 0;
            for i = 1:numel(signalsToAdd)
                signalInfo = signalsToAdd{i};

                % Check if already assigned
                alreadyAssigned = false;
                for j = 1:numel(currentAssignments)
                    if isequal(currentAssignments{j}, signalInfo)
                        alreadyAssigned = true;
                        break;
                    end
                end

                if ~alreadyAssigned
                    currentAssignments{end+1} = signalInfo;
                    addedCount = addedCount + 1;
                end
            end

            % Update assignments
            obj.AssignedSignals{tabIdx}{subplotIdx} = currentAssignments;

            % OPTIONAL: Store in property if you want both approaches
            obj.LastAddedCount = addedCount;

            % RETURN the count (this was missing!)
            % addedCount is automatically returned since it's the output parameter
        end
        function isHebrew = containsHebrew(~, text)
            % Check if text contains Hebrew characters (Unicode range 1424-1535)
            isHebrew = false;

            if isempty(text)
                return;
            end

            % Convert to double to check Unicode values
            try
                unicodeValues = double(text);
                % Hebrew characters are typically in range 1424-1535 (0x0590-0x05FF)
                hebrewRange = (unicodeValues >= 1424 & unicodeValues <= 1535);
                isHebrew = any(hebrewRange);
            catch
                % If conversion fails, assume it's not Hebrew
                isHebrew = false;
            end
        end
        % New method to ensure + tab stays at the end
        function ensurePlusTabAtEnd(obj)
            % Find the + tab
            plusTabIdx = find(cellfun(@(t) strcmp(t.Title, '+'), obj.PlotTabs));

            if ~isempty(plusTabIdx)
                % If + tab is not at the very end, move it
                if plusTabIdx < numel(obj.PlotTabs)
                    % Remove + tab from current position in PlotTabs array
                    plusTab = obj.PlotTabs{plusTabIdx};
                    obj.PlotTabs(plusTabIdx) = [];

                    % Add + tab to the end of PlotTabs array
                    obj.PlotTabs{end+1} = plusTab;
                end
            else
                % No + tab exists, create one at the end
                plusTab = uitab(obj.App.MainTabGroup, 'Title', '+');
                obj.PlotTabs{end+1} = plusTab;
            end

            % Ensure the actual UI tab order matches our array order
            obj.reorderUITabs();
        end
        function validateSelectedSubplotIdx(obj, tabIdx)
            % Ensure SelectedSubplotIdx is valid for the given tab
            if tabIdx <= numel(obj.TabLayouts)
                layout = obj.TabLayouts{tabIdx};
                maxSubplots = layout(1) * layout(2);

                if obj.SelectedSubplotIdx > maxSubplots
                    obj.SelectedSubplotIdx = 1;

                    % Update dropdown if it exists
                    if tabIdx <= numel(obj.TabControls) && ~isempty(obj.TabControls{tabIdx}) && ...
                            isfield(obj.TabControls{tabIdx}, 'SubplotDropdown')
                        obj.TabControls{tabIdx}.SubplotDropdown.Value = 'Plot 1';
                    end
                end
            end
        end

        % New method to update signal tree based on current tab
        function updateSignalTreeForCurrentTab(obj)
            % Update the signal tree to show which signals are assigned to the current subplot
            % Use the lightweight version for better performance
            obj.updateSignalTreeIndicatorsOnly();
        end

    end

    methods
        function delete(obj)
            % Clean up timer when PlotManager is destroyed
            if ~isempty(obj.TabSwitchTimer) && isvalid(obj.TabSwitchTimer)
                stop(obj.TabSwitchTimer);
                delete(obj.TabSwitchTimer);
            end
        end
    end

    methods (Access = private)
        function ensurePlusTab(obj)
            % Check if + tab already exists
            plusTabIdx = find(cellfun(@(t) strcmp(t.Title, '+'), obj.PlotTabs), 1);

            if isempty(plusTabIdx)
                % No + tab exists, create one
                plusTab = uitab(obj.App.MainTabGroup, 'Title', '+');
                obj.PlotTabs{end+1} = plusTab;

                % Don't add to other arrays since + tab has no content
                % Just ensure arrays are properly sized for real tabs only
            end

            % Set up tab selection callback if not already done
            if isempty(obj.App.MainTabGroup.SelectionChangedFcn)
                obj.setupTabCallbacks();
            end
        end
    end
end