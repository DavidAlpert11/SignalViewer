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
        GridLayouts
        TabControls
        MainTabGridLayouts
        % Add properties for stable streaming
        AxesLimits  % Store current limits to prevent jumping
        LastDataTime % Track last data time for each axes

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
                newAx.XLim = sourceAx.XLim;
                newAx.YLim = sourceAx.YLim;

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
                tempAx.XLim = sourceAx.XLim;
                tempAx.YLim = sourceAx.YLim;

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
                tempAx.XLim = sourceAx.XLim;
                tempAx.YLim = sourceAx.YLim;

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

                % Initialize limits tracking with empty values
                obj.AxesLimits{tabIdx}{i} = struct('XLim', [], 'YLim', [], 'HasData', false);
                obj.LastDataTime{tabIdx}{i} = 0;

                % Add click callback for subplot selection
                ax.ButtonDownFcn = @(src, event) obj.selectSubplot(tabIdx, i);

                % ADD COMBINED CONTEXT MENU with both data tips and export options
                cm = uicontextmenu(obj.App.UIFigure);

                % Caption editing - NEW
                uimenu(cm, 'Text', '📝 Edit Title, Caption & Description', ...
                    'MenuSelectedFcn', @(src, event) obj.App.editSubplotCaption(tabIdx, i));

                % Data tips toggle - always available
                uimenu(cm, 'Text', '🎯 Toggle Data Tips', ...
                    'MenuSelectedFcn', @(src, event) obj.toggleDataTipsForAxes(ax), ...
                    'Separator', 'on');

                % Export options - always available
                uimenu(cm, 'Text', '📊 Export to MATLAB Figure', ...
                    'MenuSelectedFcn', @(src, event) obj.exportSubplotToFigure(tabIdx, i), ...
                    'Separator', 'on');
                uimenu(cm, 'Text', '📋 Copy to Clipboard', ...
                    'MenuSelectedFcn', @(src, event) obj.copySubplotToClipboard(tabIdx, i));
                uimenu(cm, 'Text', '💾 Save as Image', ...
                    'MenuSelectedFcn', @(src, event) obj.saveSubplotAsImage(tabIdx, i));

                uimenu(cm, 'Text', '🗑️ Clear Subplot', ...
                    'MenuSelectedFcn', @(src, event) obj.clearSubplot(tabIdx, i));

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
                    sigs = assignments{k};

                    if isempty(sigs)
                        % No signals assigned - let axes auto-scale or keep existing limits
                        if shouldClearAndRecreate
                            % Only set defaults if we cleared everything and not streaming
                            if ~isStreaming
                                % Let auto-scaling handle empty axes
                                ax.XLimMode = 'auto';
                                ax.YLimMode = 'auto';
                            else
                                % During streaming, keep reasonable defaults
                                axis(ax, 'auto');
                                ax.XLimMode = 'manual';
                                ax.YLimMode = 'manual';
                            end
                        else
                            % Keep existing limits and remove all signal plots
                            obj.removeAllSignalPlots(ax);
                            ax.XLim = currentXLim;
                            ax.YLim = currentYLim;
                            ax.XLimMode = 'manual';
                            ax.YLimMode = 'manual';
                        end
                        hold(ax, 'off');
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

                    % Plot all signals
                    for j = 1:numel(sigs)
                        sigInfo = sigs{j};
                        sigName = sigInfo.Signal;
                        assignedSignalNames{end+1} = sigName;

                        T = obj.App.DataManager.DataTables{sigInfo.CSVIdx};
                        if ~ismember(sigName, T.Properties.VariableNames)
                            continue;
                        end

                        validData = ~isnan(T.(sigName));
                        if ~any(validData)
                            continue;
                        end

                        timeData = T.Time(validData);
                        signalData = T.(sigName)(validData);

                        % Apply scaling
                        scaleFactor = 1.0;
                        if obj.App.DataManager.SignalScaling.isKey(sigName)
                            scaleFactor = obj.App.DataManager.SignalScaling(sigName);
                        end
                        scaledData = signalData * scaleFactor;

                        % Collect data for limit calculation
                        allTimeData = [allTimeData; timeData];
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

                        if isStateSignal
                            % State signals: always recreate (vertical lines are simple)
                            obj.removeSignalPlot(ax, sigName);
                            obj.plotStateSignalStable(ax, timeData, scaledData, color, sigName, currentYLim);
                        else
                            % Regular signals: update existing or create new
                            if shouldClearAndRecreate
                                % Create new plot
                                h = plot(ax, timeData, scaledData, 'LineWidth', width, 'Color', color, 'DisplayName', sigName);
                                plotHandles(end+1) = h;
                                plotLabels{end+1} = sigName;
                            else
                                % Update existing plot or create if not found
                                h = obj.updateOrCreateSignalPlot(ax, sigName, timeData, scaledData, color, width);
                                if ~isempty(h)
                                    plotHandles(end+1) = h;
                                    plotLabels{end+1} = sigName;
                                end
                            end
                        end
                    end

                    % Remove plots for signals no longer assigned (only during streaming)
                    if ~shouldClearAndRecreate
                        obj.removeUnassignedSignalPlots(ax, assignedSignalNames);
                    end

                    % Show legend for regular signals
                    if ~isempty(plotHandles)
                        legend(ax, plotHandles, plotLabels, 'Location', 'best');
                    else
                        legend(ax, 'off');
                    end

                    % **Smart limit management - FORCE AUTO-SCALING FOR NON-STREAMING**
                    if ~isempty(allTimeData) && ~isempty(allValueData)
                        if isStreaming
                            % Streaming mode: manually expand limits based on data
                            obj.updateLimitsForStreaming(ax, allTimeData, allValueData, currentXLim, currentYLim, hasExistingData);
                        else
                            % Not streaming: FORCE auto-scaling immediately
                            ax.XLimMode = 'auto';
                            ax.YLimMode = 'auto';
                            axis(ax, 'auto');
                            % Switch back to manual to prevent future changes
                            ax.XLimMode = 'manual';
                            ax.YLimMode = 'manual';
                        end
                    else
                        % No data case
                        if hasExistingData && ~shouldClearAndRecreate
                            ax.XLim = currentXLim;
                            ax.YLim = currentYLim;
                            ax.XLimMode = 'manual';
                            ax.YLimMode = 'manual';
                        else
                            % Empty plot - let auto-scaling work
                            if ~isStreaming
                                ax.XLimMode = 'auto';
                                ax.YLimMode = 'auto';
                            else
                                ax.XLim = [0 10];
                                ax.YLim = [-1 1];
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
        function line = findSignalPlot(obj, ax, sigName)
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
            line = obj.findSignalPlot(ax, sigName);
            if ~isempty(line) && isvalid(line)
                delete(line);
            end
        end

        % **NEW METHOD: Remove all signal plots**
        function removeAllSignalPlots(obj, ax)
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
        function removeUnassignedSignalPlots(obj, ax, assignedSignalNames)
            if isempty(ax.Children)
                return;
            end

            % Find lines that are not in the assigned list
            linesToDelete = [];
            for i = 1:numel(ax.Children)
                child = ax.Children(i);
                if isa(child, 'matlab.graphics.chart.primitive.Line') && ...
                        isprop(child, 'DisplayName') && ...
                        ~isempty(child.DisplayName) && ...
                        ~ismember(child.DisplayName, assignedSignalNames)
                    linesToDelete = [linesToDelete, child];
                end
            end

            % Delete unassigned lines
            for line = linesToDelete
                if isvalid(line)
                    delete(line);
                end
            end
        end

        % **NEW METHOD: Update limits during streaming**
        function updateLimitsForStreaming(obj, ax, allTimeData, allValueData, currentXLim, currentYLim, hasExistingData)
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
            ax.XLim = finalXLim;
            ax.YLim = finalYLim;
            ax.XLimMode = 'manual';
            ax.YLimMode = 'manual';
        end

        % **NEW METHOD: Link all axes**
        function linkAllAxes(obj)
            allAxes = [];
            for i = 1:numel(obj.AxesArrays)
                if ~isempty(obj.AxesArrays{i})
                    for j = 1:numel(obj.AxesArrays{i})
                        ax = obj.AxesArrays{i}(j);
                        if isvalid(ax) && isgraphics(ax)
                            allAxes = [allAxes, ax];
                        end
                    end
                end
            end
            if ~isempty(allAxes)
                linkaxes(allAxes, 'x');
            end
        end

        % **UPDATED METHOD: Improved state signal plotting**
        function plotStateSignalStable(obj, ax, timeData, valueData, color, label, currentYLim)
            if length(timeData) < 2
                plot(ax, timeData, valueData, 'Color', color, 'LineWidth', 2, 'DisplayName', label);
                return;
            end

            % Use a tolerance for floating-point changes
            changeIdx = find([true; abs(diff(valueData)) > 1e-8]);

            % Use current Y limits if they exist and are reasonable
            if length(currentYLim) == 2 && currentYLim(2) > currentYLim(1) && ~isequal(currentYLim, [0 1])
                yLimits = currentYLim;
            else
                if min(valueData) ~= max(valueData)
                    yRange = max(valueData) - min(valueData);
                    yPadding = 0.1 * yRange;
                    yLimits = [min(valueData) - yPadding, max(valueData) + yPadding];
                else
                    yLimits = [min(valueData) - 0.5, max(valueData) + 0.5];
                end
            end

            if isempty(changeIdx)
                t = timeData(1);
                plot(ax, [t t], yLimits, 'Color', color, 'LineWidth', 2, 'DisplayName', label);
            else
                for k = 1:numel(changeIdx)
                    t = timeData(changeIdx(k));
                    if k == 1
                        plot(ax, [t t], yLimits, 'Color', color, 'LineWidth', 2, 'DisplayName', label);
                    else
                        plot(ax, [t t], yLimits, 'Color', color, 'LineWidth', 2);
                    end
                end
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
            % Handle tab clicks - double-click to close
            persistent lastClickTime lastClickedTab

            currentTime = now;

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

                % Update tab titles (this will hide X if only one tab remains)
                obj.updateTabTitles();

                % Ensure + tab stays at the end
                obj.ensurePlusTabAtEnd();

                % Update UI
                obj.App.UIController.updateSubplotDropdown();
                obj.updateSignalTreeForCurrentTab();
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

                fprintf('Debug: Found %d plots to include\n', size(plotsToInclude, 1));
                fprintf('Debug: Output path: %s\n', fullPath);

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
                    fprintf('Debug: PDF file created successfully at: %s\n', fullPath);

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
                    fprintf('Debug: PDF file was not created at: %s\n', fullPath);
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


        function createTitlePageContent(obj, ax, options)
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

        % Enable synchronized zoom/pan (link x-limits of all axes)
        function enableSyncZoom(obj)
            allAxes = [];
            for i = 1:numel(obj.AxesArrays)
                if ~isempty(obj.AxesArrays{i})
                    allAxes = [allAxes, obj.AxesArrays{i}(:)'];
                end
            end
            if ~isempty(allAxes)
                linkaxes(allAxes, 'x');
            end
        end
        function addTabControls(obj, tabIdx)
            % Add layout and subplot controls in row 1 of the main layout
            mainLayout = obj.MainTabGridLayouts{tabIdx};

            % Create control panel in row 1 of the main layout
            controlPanel = uipanel(mainLayout, ...
                'BackgroundColor', [0.85 0.85 0.85], ...
                'BorderType', 'line', ...
                'BorderWidth', 2, ...
                'Title', 'Layout Controls', ...
                'FontSize', 12, ...
                'FontWeight', 'bold');

            % Set the layout position AFTER creating the panel
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
                'FontWeight', 'bold', ...
                'FontSize', 11);

            rowsSpinner = uispinner(controlPanel, ...
                'Position', [75 controlY 60 25], ...
                'Limits', [1 10], ...
                'Value', currentRows, ...
                'FontSize', 10, ...
                'ValueChangedFcn', @(src, event) obj.onTabLayoutChanged(tabIdx, src.Value, []));

            uilabel(controlPanel, 'Text', 'Cols:', ...
                'Position', [150 controlY 50 25], ...
                'FontWeight', 'bold', ...
                'FontSize', 11);

            colsSpinner = uispinner(controlPanel, ...
                'Position', [205 controlY 60 25], ...
                'Limits', [1 10], ...
                'Value', currentCols, ...
                'FontSize', 10, ...
                'ValueChangedFcn', @(src, event) obj.onTabLayoutChanged(tabIdx, [], src.Value));

            % Subplot selection
            uilabel(controlPanel, 'Text', 'Current Subplot:', ...
                'Position', [290 controlY 100 25], ...
                'FontWeight', 'bold', ...
                'FontSize', 11);

            % Calculate subplot options
            nPlots = currentRows * currentCols;
            plotItems = cell(nPlots, 1);
            for i = 1:nPlots
                plotItems{i} = sprintf('Plot %d', i);
            end

            subplotDropdown = uidropdown(controlPanel, ...
                'Position', [400 controlY 120 25], ...
                'Items', plotItems, ...
                'Value', sprintf('Plot %d', obj.SelectedSubplotIdx), ...
                'FontSize', 10, ...
                'ValueChangedFcn', @(src, event) obj.onSubplotSelected(tabIdx, src.Value));

            % Store references to update them later
            obj.TabControls{tabIdx} = struct(...
                'Panel', controlPanel, ...
                'RowsSpinner', rowsSpinner, ...
                'ColsSpinner', colsSpinner, ...
                'SubplotDropdown', subplotDropdown);
        end
        % Disable synchronized zoom/pan (unlink x-limits of all axes)
        function disableSyncZoom(obj)
            allAxes = [];
            for i = 1:numel(obj.AxesArrays)
                if ~isempty(obj.AxesArrays{i})
                    allAxes = [allAxes, obj.AxesArrays{i}(:)'];
                end
            end
            if ~isempty(allAxes)
                linkaxes(allAxes, 'off');
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

                    % Clear highlights from previous tab
                    if obj.CurrentTabIdx ~= tabIdx
                        obj.App.clearSubplotHighlights(obj.CurrentTabIdx);
                    end

                    % Update current tab index
                    obj.CurrentTabIdx = tabIdx;

                    % Ensure + tab is at the end when switching tabs
                    obj.ensurePlusTabAtEnd();

                    % Update signal tree to reflect current tab's assigned signals
                    obj.updateSignalTreeForCurrentTab();

                    % Highlight current subplot in the new tab
                    obj.App.highlightSelectedSubplot(obj.CurrentTabIdx, obj.SelectedSubplotIdx);
                end
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

        function createTitlePage(obj, fig, options)
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

        function createPlotPage(obj, fig, tabIdx, subplotIdx, figureNumber, options)
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





        function copyPlotContent(obj, sourceAx, targetAx)
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
            targetAx.XLim = sourceAx.XLim;
            targetAx.YLim = sourceAx.YLim;

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





        function addCaptionToPage(obj, fig, tabIdx, subplotIdx, figureNumber)
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

            % Default caption if empty
            if isempty(caption)
                caption = sprintf('Plot for Tab %d, Subplot %d', tabIdx, subplotIdx);
            end

            % Default description if empty
            if isempty(description)
                description = 'No description provided.';
            end

            % Create caption area - larger space for text
            captionAx = axes('Parent', fig, 'Position', [0.1 0.05 0.8 0.25], 'Visible', 'off');

            % Caption title (bold)
            text(captionAx, 0.05, 0.85, sprintf('Figure %d: %s', figureNumber, caption), ...
                'FontSize', 14, 'FontWeight', 'bold', 'Units', 'normalized', ...
                'VerticalAlignment', 'top', 'Interpreter', 'none');

            % Description (normal text, wrapped)
            text(captionAx, 0.05, 0.65, description, ...
                'FontSize', 11, 'Units', 'normalized', ...
                'VerticalAlignment', 'top', 'Interpreter', 'none');

            % Add assigned signals info - FIXED: REMOVED FontStyle
            if tabIdx <= numel(obj.AssignedSignals) && ...
                    subplotIdx <= numel(obj.AssignedSignals{tabIdx})
                assignedSignals = obj.AssignedSignals{tabIdx}{subplotIdx};
                if ~isempty(assignedSignals)
                    signalNames = {};
                    for i = 1:numel(assignedSignals)
                        signalNames{end+1} = assignedSignals{i}.Signal;
                    end
                    signalText = sprintf('Signals: %s', strjoin(signalNames, ', '));

                    text(captionAx, 0.05, 0.35, signalText, ...
                        'FontSize', 10, 'Units', 'normalized', ...
                        'VerticalAlignment', 'top', 'Interpreter', 'none');
                    % REMOVED: 'FontStyle', 'italic'
                end
            end
        end
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

        function success = appendPDFPage(obj, mainPdfFile, pagePdfFile)
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

        function subplotTitle = getSubplotTitle(obj, app, tabIdx, subplotIdx)
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
        function txt = customDataTipText(obj, ~, event_obj)
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
            fprintf('Original: "%s" -> Processed: "%s"\n', text, processedText);
        end
        function isHebrew = containsHebrew(obj, text)
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


        % New method to update signal tree based on current tab
        function updateSignalTreeForCurrentTab(obj)
            % Update the signal tree to show which signals are assigned to the current subplot
            tabIdx = obj.CurrentTabIdx;
            subplotIdx = obj.SelectedSubplotIdx;

            % Clear current selection in signal tree
            if ~isempty(obj.App.SignalTree) && isvalid(obj.App.SignalTree)
                obj.App.SignalTree.SelectedNodes = [];
            end

            % Get assigned signals for current subplot
            assignedSignals = {};
            if tabIdx <= numel(obj.AssignedSignals) && ...
                    subplotIdx <= numel(obj.AssignedSignals{tabIdx})
                assignedSignals = obj.AssignedSignals{tabIdx}{subplotIdx};
            end

            % Update the visual indicators in the signal tree
            obj.updateSignalTreeVisualIndicators(assignedSignals);

            % Update the signal properties table
            if ismethod(obj.App, 'updateSignalPropsTable')
                obj.App.updateSignalPropsTable(assignedSignals);
            end
        end

    end


    methods (Access = private)
        function ensurePlusTab(obj)
            % Check if + tab already exists
            plusTabIdx = find(cellfun(@(t) strcmp(t.Title, '+'), obj.PlotTabs));

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