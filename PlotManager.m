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
        function obj = PlotManager(app)
            obj.App = app;
            obj.PlotTabs = {};
            obj.AxesArrays = {};
            obj.AssignedSignals = {};
            obj.TabLayouts = {};
            obj.GridLayouts = {};
            obj.LinkedAxes = matlab.graphics.axis.Axes.empty;
            obj.CurrentTabIdx = 1;
            obj.SelectedSubplotIdx = 1;
            % Don't create the first tab here - do it after PlotManager is assigned
        end

        function initialize(obj)
            % Call this after PlotManager is assigned to app
            obj.createFirstTab();
        end

        function createFirstTab(obj)
            tab = uitab(obj.App.MainTabGroup, 'Title', 'Tab 1', ...
                'BackgroundColor', [0.1 0.1 0.1]);
            obj.PlotTabs{1} = tab;
            obj.GridLayouts{1} = uigridlayout(tab, [2, 1], ...
                'BackgroundColor', [0.1 0.1 0.1]);
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
        end

        function createSubplotsForTab(obj, tabIdx, rows, cols)
            if tabIdx > numel(obj.PlotTabs)
                return;
            end

            obj.TabLayouts{tabIdx} = [rows, cols];

            if ~isempty(obj.AxesArrays{tabIdx})
                for ax = obj.AxesArrays{tabIdx}
                    if isvalid(ax)
                        obj.LinkedAxes(obj.LinkedAxes == ax) = [];
                        delete(ax);
                    end
                end
            end

            delete(obj.GridLayouts{tabIdx});
            obj.GridLayouts{tabIdx} = uigridlayout(obj.PlotTabs{tabIdx}, [rows, cols], ...
                'BackgroundColor', [0.1 0.1 0.1]);

            nPlots = rows * cols;
            obj.AxesArrays{tabIdx} = matlab.ui.control.UIAxes.empty;

            obj.AssignedSignals{tabIdx} = cell(nPlots, 1);
            for i = 1:nPlots
                obj.AssignedSignals{tabIdx}{i} = {};
            end

            for i = 1:nPlots
                ax = uiaxes(obj.GridLayouts{tabIdx});
                
                % Enhanced subplot styling
                ax.Title.String = sprintf('Plot %d', i);
                ax.Title.Color = [0.9 0.9 0.9];
                ax.Title.FontSize = 12;
                ax.XLabel.String = 'Time';
                ax.YLabel.String = 'Value';
                ax.XLabel.Color = [0.8 0.8 0.8];
                ax.YLabel.Color = [0.8 0.8 0.8];
                ax.Color = [0.05 0.05 0.05];  % Dark plot background
                ax.GridColor = [0.3 0.3 0.3];
                ax.GridAlpha = 0.5;
                ax.XColor = [0.7 0.7 0.7];
                ax.YColor = [0.7 0.7 0.7];
                
                grid(ax, 'on');
                hold(ax, 'on');
                obj.AxesArrays{tabIdx}(i) = ax;
                obj.LinkedAxes(end+1) = ax;
                
                % Add click callback for subplot selection
                ax.ButtonDownFcn = @(src, event) obj.selectSubplot(tabIdx, i);
            end

            if numel(obj.LinkedAxes) > 1
                linkaxes(obj.LinkedAxes, 'x');
            end
            
            % Highlight the selected subplot
            obj.App.highlightSelectedSubplot(tabIdx, obj.SelectedSubplotIdx);
        end

        function selectSubplot(obj, tabIdx, subplotIdx)
            % Handle subplot selection with visual feedback
            obj.SelectedSubplotIdx = subplotIdx;
            obj.App.highlightSelectedSubplot(tabIdx, subplotIdx);
            
            % Update the dropdown
            obj.App.SubplotDropdown.Value = sprintf('Plot %d', subplotIdx);
            
            % Update signal table
            obj.App.UIController.updateSignalCheckboxes();
        end

        function refreshPlots(obj, tabIndices)
            if nargin < 2
                tabIndices = 1:numel(obj.AxesArrays);
            end

            if isempty(obj.App.DataManager.DataBuffer)
                return;
            end

            for tabIdx = tabIndices
                if tabIdx > numel(obj.AxesArrays) || isempty(obj.AxesArrays{tabIdx})
                    continue;
                end

                axes = obj.AxesArrays{tabIdx};
                assignments = obj.AssignedSignals{tabIdx};

                for k = 1:numel(axes)
                    ax = axes(k);
                    sigs = assignments{k};
                    cla(ax); hold(ax, 'on');
                    
                    % Maintain enhanced styling after clearing
                    ax.Color = [0.05 0.05 0.05];
                    ax.GridColor = [0.3 0.3 0.3];
                    ax.GridAlpha = 0.5;
                    ax.XLabel.Color = [0.8 0.8 0.8];
                    ax.YLabel.Color = [0.8 0.8 0.8];
                    ax.Title.Color = [0.9 0.9 0.9];

                    if isempty(sigs)
                        continue;
                    end

                    for j = 1:numel(sigs)
                        s = sigs{j};
                        if ~ismember(s, obj.App.DataManager.DataBuffer.Properties.VariableNames)
                            continue;
                        end

                        validData = ~isnan(obj.App.DataManager.DataBuffer.(s));
                        if ~any(validData)
                            continue;
                        end

                        timeData = obj.App.DataManager.DataBuffer.Time(validData);
                        scaleFactor = 1.0;
                        if obj.App.DataManager.SignalScaling.isKey(s)
                            scaleFactor = obj.App.DataManager.SignalScaling(s);
                        end
                        scaledData = obj.App.DataManager.DataBuffer.(s)(validData) * scaleFactor;

                        isStateSignal = false;
                        if obj.App.DataManager.StateSignals.isKey(s)
                            isStateSignal = obj.App.DataManager.StateSignals(s);
                        end

                        label = s;
                        if scaleFactor ~= 1.0
                            label = sprintf('%s (×%.2f)', label, scaleFactor);
                        end
                        if isStateSignal
                            label = sprintf('%s [STATE]', label);
                        end

                        % Use enhanced color scheme
                        color = obj.App.Colors(mod(j-1, size(obj.App.Colors,1)) + 1, :);

                        if isStateSignal
                            obj.plotStateSignal(ax, timeData, scaledData, color, label);
                        else
                            plot(ax, timeData, scaledData, 'LineWidth', 2, ...
                                'Color', color, 'DisplayName', label);
                        end
                    end

                    if ~isempty(ax.Children)
                        legend(ax, 'show', 'Location', 'best', ...
                            'TextColor', [0.9 0.9 0.9], ...
                            'Color', [0.2 0.2 0.2 0.8]);
                    end

                    if obj.App.AutoScaleCheckbox.Value
                        axis(ax, 'tight');
                    end

                    grid(ax, 'on');
                    ax.XLabel.String = 'Time';
                    ax.YLabel.String = 'Value';
                end
            end
            
            % Restore highlight after refresh
            obj.App.highlightSelectedSubplot(obj.CurrentTabIdx, obj.SelectedSubplotIdx);
            
            % Update visual feedback in signal table
            obj.App.updateSignalTableVisualFeedback();
        end

        function plotStateSignal(obj, ax, timeData, valueData, color, label)
            if length(timeData) < 2
                return;
            end
            changeIdx = find([true; diff(valueData) ~= 0]);
            yLimits = ylim(ax);
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

        function exportToPDF(obj)
            if obj.CurrentTabIdx > numel(obj.AxesArrays) || isempty(obj.AxesArrays{obj.CurrentTabIdx})
                uialert(obj.App.UIFigure, 'No plots to export.', 'Info');
                return;
            end

            [file, path] = uiputfile('*.pdf', 'Export Plots to PDF');
            if isequal(file, 0), return; end

            try
                exportFig = figure('Visible', 'off', 'Position', [100 100 800 600], ...
                    'Color', [0.1 0.1 0.1]);

                axes_array = obj.AxesArrays{obj.CurrentTabIdx};
                [rows, cols] = size(reshape(1:numel(axes_array), obj.TabLayouts{obj.CurrentTabIdx}));

                for i = 1:numel(axes_array)
                    subplot(rows, cols, i);
                    copyobj(allchild(axes_array(i)), gca);
                    title(axes_array(i).Title.String, 'Color', 'white');
                    xlabel(axes_array(i).XLabel.String, 'Color', 'white');
                    ylabel(axes_array(i).YLabel.String, 'Color', 'white');
                    set(gca, 'Color', [0.05 0.05 0.05], 'XColor', [0.8 0.8 0.8], 'YColor', [0.8 0.8 0.8]);
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
    end
end