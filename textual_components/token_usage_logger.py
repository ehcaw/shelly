from textual_plotext import PlotextPlot
import plotext as plt
import asyncio

class TokenUsagePlot(PlotextPlot):
    def __init__(self,*args, **kwargs):
        super().__init__()
        self.id = kwargs["id"]
        self.operation_counter = 0
        self.operations = []
        self.input_token_usage = 0
        self.input_tokens = []
        self.output_token_usage = 0
        self.output_tokens = []
        self.total_token_usage = 0
        self.token_usage = []

    def update_chart(self, input_tokens, output_tokens):
        self.input_tokens.append(input_tokens)
        self.output_tokens.append(output_tokens)
        total_tokens = input_tokens + output_tokens
        self.token_usage.append(total_tokens)
        self.total_token_usage += total_tokens
        self.operation_counter += 1
        self.operations.append(self.operation_counter)

        if len(self.token_usage) > 20:
            self.token_usage.pop(0)

        plt.clf()
        plt.plot(self.operations, self.token_usage)
        plt.title(f'Total Tokens: {self.total_token_usage}')
        self.refresh()
