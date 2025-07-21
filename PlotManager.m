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
            obj.LinkedAxes = matlab.graphics.axis.Axes.empty;
            obj.CurrentTabIdx = 1;
            obj.SelectedSubplotIdx = 1;
        end

        % Initialize the plot manager (create the first tab)
        function initialize(obj)
            obj.createFirstTab();
        end

        % Create the first tab with default layout and context menu
        function createFirstTab(obj)
            % Create first tab with LIGHT MODE styling
            tab = uitab(obj.App.MainTabGroup, 'Title', 'Tab 1 ❌', ...
                'BackgroundColor', [0.98 0.98 0.98]);
            % Add context menu for closing
            cm = uicontextmenu(obj.App.UIFigure);
            uimenu(cm, 'Text', 'Close Tab', 'MenuSelectedFcn', @(src, event) obj.deleteTabByHandle(tab));
            tab.ContextMenu = cm;
            obj.PlotTabs{1} = tab;
            obj.GridLayouts{1} = uigridlayout(tab, [2, 1], ...
                'BackgroundColor', [0.98 0.98 0.98]);   % Light background
            obj.AxesArrays{1} = matlab.ui.control.UIAxes.empty;

            obj.AssignedSignals{1} = cell(2, 1);
            for i = 1:2
                obj.AssignedSignals{1}{i} = {};
            end

            obj.TabLayouts{1} = [2, 1];
            obj.createSubplotsForTab(1, 2, 1);
            obj.CurrentTabIdx = 1;
            
            % Highlight the first subplot
            obj.App.highlightSelectedSubplot(1, 1);

            % Ensure the + tab exists
            obj.ensurePlusTab();
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

            % Create new grid layout and uiaxes
            obj.GridLayouts{tabIdx} = uigridlayout(obj.PlotTabs{tabIdx}, [rows, cols], 'BackgroundColor', [1 1 1]);
            nPlots = rows * cols;
            obj.AxesArrays{tabIdx} = gobjects(1, nPlots);
            for i = 1:nPlots
                ax = uiaxes(obj.GridLayouts{tabIdx});
                ax.Layout.Row = ceil(i/cols);
                ax.Layout.Column = mod(i-1, cols)+1;
                ax.Color = [1 1 1];
                ax.Box = 'on';
                ax.XLabel.String = 'Time';
                ax.YLabel.String = 'Value';
                % Add click callback for subplot selection
                ax.ButtonDownFcn = @(src, event) obj.selectSubplot(tabIdx, i);
                obj.AxesArrays{tabIdx}(i) = ax;
            end
            % Immediately refresh plots for this tab so checked signals are shown
            obj.App.PlotManager.refreshPlots(tabIdx);
            % Highlight the selected subplot
            obj.App.highlightSelectedSubplot(tabIdx, obj.SelectedSubplotIdx);
        end

        % Refresh all plots for the specified tab indices. If no indices are given, refreshes all tabs.
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
            for tabIdx = tabIndices
                if tabIdx > numel(obj.AxesArrays) || isempty(obj.AxesArrays{tabIdx})
                    continue;
                end
                axesArr = obj.AxesArrays{tabIdx};
                assignments = obj.AssignedSignals{tabIdx};
                n = min(numel(axesArr), numel(assignments));
                for k = 1:n
                    ax = axesArr(k);
                    % Instead of cla(ax), delete all children
                    delete(ax.Children);
                    grid(ax, 'on');
                    ax.XGrid = 'on';
                    ax.YGrid = 'on';
                    ax.XMinorGrid = 'on';
                    ax.YMinorGrid = 'on';
                    hold(ax, 'on');
                    sigs = assignments{k};
                    if isempty(sigs)
                        axis(ax, 'auto');
                        ax.XLimMode = 'auto';
                        ax.YLimMode = 'auto';
                        hold(ax, 'off');
                        continue;
                    end
                    % Use axes ColorOrder for default colors
                    colorOrder = ax.ColorOrder;
                    nColors = size(colorOrder,1);
                    regularHandles = gobjects(1, numel(sigs));
                    regLabels = {};
                    colorIdx = 1;
                    for j = 1:numel(sigs)
                        sigInfo = sigs{j};
                        sigName = sigInfo.Signal;
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
                        scaleFactor = 1.0;
                        if obj.App.DataManager.SignalScaling.isKey(sigName)
                            scaleFactor = obj.App.DataManager.SignalScaling(sigName);
                        end
                        scaledData = signalData * scaleFactor;
                        % Use custom color and line width if set, else use ColorOrder
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
                        isStateSignal = false;
                        if obj.App.DataManager.StateSignals.isKey(sigName)
                            isStateSignal = obj.App.DataManager.StateSignals(sigName);
                        end
                        if isStateSignal
                            % Plot state signal as vertical lines
                            yLimits = ylim(ax);
                            if isequal(yLimits, [0 1]) || diff(yLimits) == 0
                                if min(scaledData) ~= max(scaledData)
                                    yLimits = [min(scaledData) max(scaledData)];
                                else
                                    yLimits = [min(scaledData)-0.5, max(scaledData)+0.5];
                                end
                                ylim(ax, yLimits);
                            end
                            changeIdx = find([true; abs(diff(scaledData)) > 1e-8]);
                            for m = 1:numel(changeIdx)
                                t = timeData(changeIdx(m));
                                plot(ax, [t t], ylim(ax), 'Color', color, 'LineWidth', width);
                            end
                        else
                            h = plot(ax, timeData, scaledData, 'LineWidth', width, 'Color', color, 'DisplayName', sigName);
                            regularHandles(j) = h;
                            regLabels{end+1} = sigName;
                        end
                    end
                    % Only show legend if there are regular (non-state) signals
                    regHandles = regularHandles(isgraphics(regularHandles));
                    if ~isempty(regHandles)
                        legend(ax, regHandles, regLabels, 'Location', 'best');
                    else
                        legend(ax, 'off');
                    end
                    % Always autoscale after plotting
                    axis(ax, 'auto');
                    ax.XLimMode = 'auto';
                    ax.YLimMode = 'auto';
                    drawnow;
                    hold(ax, 'off');
                end
            end
            % Link all axes in all tabs on the x-axis
            allAxes = [];
            for i = 1:numel(obj.AxesArrays)
                if ~isempty(obj.AxesArrays{i})
                    allAxes = [allAxes, obj.AxesArrays{i}(:)'];
                end
            end
            if ~isempty(allAxes)
                linkaxes(allAxes, 'x');
                % Always autoscale all axes after linking
                for ax = allAxes
                    axis(ax, 'auto');
                end
            end
            % Restore highlight after refresh
            obj.App.highlightSelectedSubplot(obj.CurrentTabIdx, obj.SelectedSubplotIdx);
        end

        function updateAllPlotsForStreaming(obj)
            % Call this method periodically or after new data is streamed in
            obj.refreshPlots();
        end

        % Plot a state signal as vertical lines at value changes
        function plotStateSignal(obj, ax, timeData, valueData, color, label)
            if length(timeData) < 2
                % Plot a dummy invisible line to set xlim
                plot(ax, timeData, valueData, 'k', 'Visible', 'off');
                return;
            end
            % Use a tolerance for floating-point changes
            changeIdx = find([true; abs(diff(valueData)) > 1e-8]);
            yLimits = ylim(ax);
            % If yLimits are [0,1] or degenerate, set to a reasonable default
            if isequal(yLimits, [0 1]) || diff(yLimits) == 0
                if min(valueData) ~= max(valueData)
                    yLimits = [min(valueData) max(valueData)];
                else
                    yLimits = [min(valueData)-0.5, max(valueData)+0.5];
                end
                ylim(ax, yLimits);
            end
            if isempty(changeIdx)
                % No changes, plot a single vertical line at the start
                t = timeData(1);
                plot(ax, [t t], yLimits, 'Color', color, 'LineWidth', 2, 'DisplayName', label);
            else
                for k = 1:numel(changeIdx)
                    t = timeData(changeIdx(k));
                    if k == 1
                        plot(ax, [t t], yLimits, 'Color', color, ...
                            'LineWidth', 2, 'DisplayName', label);
                    else
                        plot(ax, [t t], yLimits, 'Color', color, 'LineWidth', 2);
                    end
                end
            end
        end

        function selectSubplot(obj, tabIdx, subplotIdx)
            % Handle subplot selection with visual feedback
            obj.SelectedSubplotIdx = subplotIdx;
            obj.App.highlightSelectedSubplot(tabIdx, subplotIdx);
            
            % Update the dropdown only if the value exists
            val = sprintf('Plot %d', subplotIdx);
            if any(strcmp(val, obj.App.SubplotDropdown.Items))
                obj.App.SubplotDropdown.Value = val;
            end
        end

        function addNewTab(obj, ~, ~)
            % Always use default layout [2,1]
            rows = 2; cols = 1;
            tabNum = numel(obj.PlotTabs) + 1;
            plusTabIdx = find(cellfun(@(t) strcmp(t.Title, '+'), obj.PlotTabs));
            if ~isempty(plusTabIdx)
                tab = uitab(obj.App.MainTabGroup, 'Title', sprintf('Tab %d ❌', plusTabIdx), ...
                    'BackgroundColor', [0.98 0.98 0.98]);
                cm = uicontextmenu(obj.App.UIFigure);
                uimenu(cm, 'Text', 'Close Tab', 'MenuSelectedFcn', @(src, event) obj.deleteTabByHandle(tab));
                tab.ContextMenu = cm;
                obj.PlotTabs = [obj.PlotTabs(1:plusTabIdx-1), {tab}, obj.PlotTabs(plusTabIdx:end)];
                obj.GridLayouts = [obj.GridLayouts(1:plusTabIdx-1), {uigridlayout(tab, [rows, cols], 'BackgroundColor', [0.98 0.98 0.98])}, obj.GridLayouts(plusTabIdx:end)];
                obj.AxesArrays = [obj.AxesArrays(1:plusTabIdx-1), {matlab.ui.control.UIAxes.empty}, obj.AxesArrays(plusTabIdx:end)];
                obj.AssignedSignals = [obj.AssignedSignals(1:plusTabIdx-1), {{}}, obj.AssignedSignals(plusTabIdx:end)];
                obj.TabLayouts = [obj.TabLayouts(1:plusTabIdx-1), {[rows, cols]}, obj.TabLayouts(plusTabIdx:end)];
                tabNum = plusTabIdx;
            else
                tab = uitab(obj.App.MainTabGroup, 'Title', sprintf('Tab %d ❌', tabNum), ...
                    'BackgroundColor', [0.98 0.98 0.98]);
                cm = uicontextmenu(obj.App.UIFigure);
                uimenu(cm, 'Text', 'Close Tab', 'MenuSelectedFcn', @(src, event) obj.deleteTabByHandle(tab));
                tab.ContextMenu = cm;
                obj.PlotTabs{end+1} = tab;
                obj.GridLayouts{end+1} = uigridlayout(tab, [rows, cols], 'BackgroundColor', [0.98 0.98 0.98]);
                obj.AxesArrays{end+1} = matlab.ui.control.UIAxes.empty;
                obj.AssignedSignals{end+1} = {};
                obj.TabLayouts{end+1} = [rows, cols];
            end
            obj.createSubplotsForTab(tabNum, rows, cols);
            obj.CurrentTabIdx = tabNum;
            obj.App.MainTabGroup.SelectedTab = tab;
            obj.ensurePlusTab();
        end
        
        function deleteCurrentTab(obj)
            % Delete current tab (prevent deleting last tab)
            if numel(obj.PlotTabs) <= 2 % Only allow if more than one real tab (+ tab doesn't count)
                return;
            end
            
            currentIdx = obj.CurrentTabIdx;
            % Don't allow deleting the + tab
            if strcmp(obj.PlotTabs{currentIdx}.Title, '+')
                return;
            end
            
            % Remove tab and associated data
            delete(obj.PlotTabs{currentIdx});
            obj.PlotTabs(currentIdx) = [];
            obj.GridLayouts(currentIdx) = [];
            obj.AxesArrays(currentIdx) = [];
            obj.AssignedSignals(currentIdx) = [];
            obj.TabLayouts(currentIdx) = [];
            
            % Update current tab index
            if currentIdx > numel(obj.PlotTabs)-1
                obj.CurrentTabIdx = numel(obj.PlotTabs)-1;
            end
            
            % Select the new current tab (not the + tab)
            obj.App.MainTabGroup.SelectedTab = obj.PlotTabs{obj.CurrentTabIdx};
            obj.ensurePlusTab();
        end
        
        function deleteTabByHandle(obj, tab)
            idx = find(cellfun(@(t) t == tab, obj.PlotTabs));
            if ~isempty(idx)
                obj.CurrentTabIdx = idx;
                obj.deleteCurrentTab();
            end
        end

        function changeTabLayout(obj, tabIdx, rows, cols)
            % Change layout of specific tab
            if tabIdx <= numel(obj.PlotTabs)
                obj.createSubplotsForTab(tabIdx, rows, cols);
            end
        end

        function exportToPDF(obj)
            if obj.CurrentTabIdx > numel(obj.AxesArrays) || isempty(obj.AxesArrays{obj.CurrentTabIdx})
                uialert(obj.App.UIFigure, 'No plots to export.', 'Info');
                return;
            end

            [file, path] = uiputfile('*.pdf', 'Export Plots to PDF');
            if isequal(file, 0), return; end

            try
                % LIGHT MODE export styling
                exportFig = figure('Visible', 'off', 'Position', [100 100 800 600], ...
                    'Color', [1 1 1]);  % White background

                axes_array = obj.AxesArrays{obj.CurrentTabIdx};
                [rows, cols] = size(reshape(1:numel(axes_array), obj.TabLayouts{obj.CurrentTabIdx}));

                for i = 1:numel(axes_array)
                    subplot(rows, cols, i);
                    copyobj(allchild(axes_array(i)), gca);
                    title(axes_array(i).Title.String, 'Color', 'black');
                    xlabel(axes_array(i).XLabel.String, 'Color', 'black');
                    ylabel(axes_array(i).YLabel.String, 'Color', 'black');
                    set(gca, 'Color', [1 1 1], 'XColor', [0.15 0.15 0.15], 'YColor', [0.15 0.15 0.15]);
                    grid on;
                end

                print(exportFig, fullfile(path, file), '-dpdf', '-fillpage');
                close(exportFig);

                uialert(obj.App.UIFigure, '✅ PDF exported successfully!', 'Success');
            catch ME
                uialert(obj.App.UIFigure, ['❌ Export failed: ' ME.message], 'Error');
            end
        end

        function resetZoom(obj)
            if obj.CurrentTabIdx <= numel(obj.AxesArrays)
                for ax = obj.AxesArrays{obj.CurrentTabIdx}
                    axis(ax, 'auto');
                end
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

        % Enable data cursor mode (data tips) for all axes
        function enableCursorMode(obj)
            for i = 1:numel(obj.AxesArrays)
                if ~isempty(obj.AxesArrays{i})
                    for ax = obj.AxesArrays{i}
                        try
                            ax.Interactions = [dataTipInteraction];
                        end
                    end
                end
            end
        end

        % Disable data cursor mode, restore default pan/zoom for all axes
        function disableCursorMode(obj)
            for i = 1:numel(obj.AxesArrays)
                if ~isempty(obj.AxesArrays{i})
                    for ax = obj.AxesArrays{i}
                        try
                            ax.Interactions = [panInteraction zoomInteraction];
                        end
                    end
                end
            end
        end
    end

    methods (Access = private)
        function ensurePlusTab(obj)
            % Remove any existing + tab
            plusTabIdx = find(cellfun(@(t) strcmp(t.Title, '+'), obj.PlotTabs));
            if ~isempty(plusTabIdx)
                delete(obj.PlotTabs{plusTabIdx});
                obj.PlotTabs(plusTabIdx) = [];
                obj.GridLayouts(plusTabIdx) = [];
                obj.AxesArrays(plusTabIdx) = [];
                obj.AssignedSignals(plusTabIdx) = [];
                obj.TabLayouts(plusTabIdx) = [];
            end
            % Add + tab at the end (no close icon)
            plusTab = uitab(obj.App.MainTabGroup, 'Title', '+');
            obj.PlotTabs{end+1} = plusTab;
        end
    end
end